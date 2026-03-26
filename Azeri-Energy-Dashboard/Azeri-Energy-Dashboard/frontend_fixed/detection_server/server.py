"""
Detection backend server (port 8000).
Uses YOLO + SAHI sliced inference with the tl_defect_cn1 best.pt weights.
Provides batch upload, per-image detection, Socket.IO progress, and results.

GPU pipeline: FP16, multi-scale inference (640+1280), batched, CUDA-pinned,
parallel video workers, threaded read/annotate/write architecture.
"""

import asyncio
import io
import os
import time
import uuid
import threading
import queue
import shutil
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import socketio
import uvicorn

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
WEIGHTS_PATH = Path(r"C:\Users\ehtis\Downloads\ginger_1_FE\tl_defect_cn1\weights\best.pt")
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

GPU_BATCH = 16          # frames per GPU batch (safe for 16GB VRAM with FP16)
READ_AHEAD = 64         # reader thread buffer
ANNOTATE_THREADS = 4    # CPU threads for drawing bboxes

# ---------------------------------------------------------------------------
# GPU detection & CUDA setup
# ---------------------------------------------------------------------------
def _select_device() -> str:
    import torch
    if torch.cuda.is_available():
        torch.cuda.init()
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"[GPU] {name} | {vram:.1f} GB VRAM | CUDA {torch.version.cuda}")
        torch.backends.cudnn.benchmark = True
        return "0"
    print("[WARN] CUDA not available, using CPU")
    return "cpu"

DEVICE = _select_device()
USE_HALF = DEVICE != "cpu"

# ---------------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------------
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Detection Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")

# ---------------------------------------------------------------------------
# Thread pools
# ---------------------------------------------------------------------------
_annotate_pool = ThreadPoolExecutor(max_workers=ANNOTATE_THREADS, thread_name_prefix="ann")

# ---------------------------------------------------------------------------
# Model (lazy-loaded once, pinned to GPU, warmed up)
# ---------------------------------------------------------------------------
_model = None
_model_lock = threading.Lock()
_sahi_det_model = None
_sahi_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from ultralytics import YOLO
                import torch
                print(f"[INFO] Loading YOLO model from {WEIGHTS_PATH} ...")
                _model = YOLO(str(WEIGHTS_PATH))
                if DEVICE != "cpu":
                    dev = torch.device(f"cuda:{DEVICE}")
                    _model.to(dev)
                    # Warmup: compile CUDA kernels + JIT so first real batch is instant
                    dummy = [np.zeros((640, 640, 3), dtype=np.uint8)] * 4
                    _model.predict(dummy, imgsz=640, device=DEVICE, verbose=False)
                    torch.cuda.synchronize()
                    vram_used = torch.cuda.memory_allocated(0) / (1024**3)
                    print(f"[GPU] Model pinned + warmed up | VRAM: {vram_used:.2f} GB")
                print(f"[INFO] Model loaded. {len(_model.names)} classes")
    return _model


def get_sahi_model(confidence: float = 0.25):
    """Cached SAHI AutoDetectionModel wrapper — avoids re-creating every call."""
    global _sahi_det_model
    sahi_device = f"cuda:{DEVICE}" if DEVICE != "cpu" else "cpu"
    if _sahi_det_model is None or abs(_sahi_det_model._confidence - confidence) > 0.001:
        with _sahi_lock:
            from sahi import AutoDetectionModel
            model = get_model()
            _sahi_det_model = AutoDetectionModel.from_pretrained(
                model_type="ultralytics",
                model=model,
                confidence_threshold=confidence,
                device=sahi_device,
            )
            _sahi_det_model._confidence = confidence
    return _sahi_det_model


# ---------------------------------------------------------------------------
# Job store (in-memory; fine for single-server use)
# ---------------------------------------------------------------------------
jobs: dict[str, dict] = {}


def _new_job(total: int, confidence: float, slice_size: int, overlap: float, source: str = "rgb") -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "total": total,
        "confidence": confidence,
        "slice_size": slice_size,
        "overlap": overlap,
        "source": source,
        "files": {},          # file_id -> {filename, status, ...}
        "results": [],        # finished results
        "completed": 0,
        "status": "active",
        "created_at": time.time(),
    }
    jobs[job_id] = job
    return job


# ---------------------------------------------------------------------------
# SAHI sliced inference
# ---------------------------------------------------------------------------
def run_sahi_detection(
    img: np.ndarray,
    confidence: float = 0.25,
    slice_size: int = 640,
    overlap: float = 0.2,
    job_id: str = "",
    file_id: str = "",
    loop: Optional[asyncio.AbstractEventLoop] = None,
):
    """Run YOLO + SAHI on a single image. Returns list[Detection]."""
    from sahi.predict import get_sliced_prediction

    model = get_model()
    detection_model = get_sahi_model(confidence)

    def _emit_progress(current: int, total_steps: int, pct: int):
        if loop and job_id:
            asyncio.run_coroutine_threadsafe(
                sio.emit("detection_progress", {
                    "job_id": job_id,
                    "file_id": file_id,
                    "current": current,
                    "total_steps": total_steps,
                    "percent": pct,
                }),
                loop,
            )

    # Full-image prediction on GPU (FP32 — avoids half/float dtype mismatch)
    _emit_progress(0, 2, 5)
    full_results = model.predict(img, conf=confidence, device=DEVICE, verbose=False)
    full_dets = []
    for r in full_results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            full_dets.append({
                "bbox": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_id": cls_id,
                "class_name": model.names.get(cls_id, str(cls_id)),
                "source": "full",
            })
    _emit_progress(1, 2, 40)

    # SAHI sliced prediction (also on GPU)
    sahi_result = get_sliced_prediction(
        img,
        detection_model,
        slice_height=slice_size,
        slice_width=slice_size,
        overlap_height_ratio=overlap,
        overlap_width_ratio=overlap,
        verbose=0,
    )
    _emit_progress(2, 2, 85)

    sahi_dets = []
    for pred in sahi_result.object_prediction_list:
        bbox = pred.bbox.to_xyxy()
        sahi_dets.append({
            "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
            "confidence": float(pred.score.value),
            "class_id": int(pred.category.id),
            "class_name": pred.category.name,
            "source": "sahi",
        })

    all_dets = full_dets + sahi_dets
    if len(all_dets) > 0:
        all_dets = _nms_merge(all_dets, iou_threshold=0.5)

    return all_dets


def _nms_merge(dets: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Simple NMS merge across detections from different sources."""
    if not dets:
        return dets

    boxes = np.array([d["bbox"] for d in dets], dtype=np.float32)
    scores = np.array([d["confidence"] for d in dets], dtype=np.float32)

    indices = cv2.dnn.NMSBoxes(
        bboxes=[[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in boxes],
        scores=scores.tolist(),
        score_threshold=0.01,
        nms_threshold=iou_threshold,
    )
    if len(indices) == 0:
        return []
    keep = indices.flatten().tolist()
    return [dets[i] for i in keep]


# ---------------------------------------------------------------------------
# Annotate image with bounding boxes (in-place for video speed)
# ---------------------------------------------------------------------------
COLORS = [
    (0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 255, 0),
    (255, 128, 0), (128, 0, 255), (0, 128, 255), (255, 0, 128),
]


def annotate_image(img: np.ndarray, dets: list[dict], copy: bool = True) -> np.ndarray:
    """Draw bounding boxes. Set copy=False for video frames (faster, in-place)."""
    canvas = img.copy() if copy else img
    for det in dets:
        x1, y1, x2, y2 = int(det["bbox"][0]), int(det["bbox"][1]), int(det["bbox"][2]), int(det["bbox"][3])
        cls_id = det.get("class_id", 0)
        color = COLORS[cls_id % len(COLORS)]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f'{det["class_name"]} {det["confidence"]:.0%}'
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(canvas, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(canvas, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return canvas


# ---------------------------------------------------------------------------
# Process a single file (runs in thread pool)
# ---------------------------------------------------------------------------
def process_file(job_id: str, file_id: str, img_bytes: bytes, filename: str,
                 confidence: float, slice_size: int, overlap: float,
                 loop: asyncio.AbstractEventLoop):
    """Process one image: detect, annotate, save thumb+annotated, return result dict."""
    t0 = time.time()

    # Decode image
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"file_id": file_id, "filename": filename, "error": "Cannot decode image"}

    # Emit start
    asyncio.run_coroutine_threadsafe(
        sio.emit("detection_start", {"job_id": job_id, "file_id": file_id, "filename": filename}),
        loop,
    )

    # Run detection
    dets = run_sahi_detection(img, confidence, slice_size, overlap, job_id, file_id, loop)

    # Create output dir
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    # Save thumbnail (original resized)
    thumb_path = job_dir / f"{file_id}_thumb.jpg"
    h, w = img.shape[:2]
    scale = min(640 / w, 640 / h, 1.0)
    thumb = cv2.resize(img, (int(w * scale), int(h * scale)))
    cv2.imwrite(str(thumb_path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # Save annotated
    annotated = annotate_image(img, dets)
    ann_path = job_dir / f"{file_id}_annotated.jpg"
    cv2.imwrite(str(ann_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])

    elapsed_ms = (time.time() - t0) * 1000
    confs = [d["confidence"] for d in dets]

    stats = {
        "total_defects": len(dets),
        "avg_confidence": float(np.mean(confs)) if confs else 0,
        "max_confidence": float(max(confs)) if confs else 0,
        "min_confidence": float(min(confs)) if confs else 0,
        "processing_time_ms": round(elapsed_ms),
    }

    return {
        "file_id": file_id,
        "filename": filename,
        "thumb_url": f"/results/{job_id}/{file_id}_thumb.jpg",
        "annotated_url": f"/results/{job_id}/{file_id}_annotated.jpg",
        "detections": dets,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Background worker: processes queued files for a job
# ---------------------------------------------------------------------------
async def _worker(job_id: str):
    """Process files as they arrive for this job."""
    job = jobs.get(job_id)
    if not job:
        return

    loop = asyncio.get_event_loop()

    while True:
        # Find next unprocessed file
        pending_file = None
        for fid, fdata in job["files"].items():
            if fdata["status"] == "pending":
                fdata["status"] = "processing"
                pending_file = (fid, fdata)
                break

        if pending_file is None:
            all_finished = (
                len(job["files"]) >= job["total"]
                and all(f["status"] in ("done", "error") for f in job["files"].values())
            )
            if all_finished:
                break
            await asyncio.sleep(0.3)
            if time.time() - job["created_at"] > 600:
                break
            continue

        fid, fdata = pending_file
        try:
            result = await loop.run_in_executor(
                None,
                process_file,
                job_id, fid, fdata["bytes"], fdata["filename"],
                job["confidence"], job["slice_size"], job["overlap"],
                loop,
            )

            if "error" in result:
                fdata["status"] = "error"
                await sio.emit("detection_result", {
                    "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
                    "error": result["error"], "completed": job["completed"], "total": job["total"],
                })
            else:
                fdata["status"] = "done"
                job["results"].append(result)
                job["completed"] += 1

                await sio.emit("detection_result", {
                    "job_id": job_id,
                    **result,
                    "completed": job["completed"],
                    "total": job["total"],
                })

            # Free memory
            fdata.pop("bytes", None)

        except Exception as e:
            fdata["status"] = "error"
            job["completed"] += 1
            await sio.emit("detection_result", {
                "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
                "error": str(e), "completed": job["completed"], "total": job["total"],
            })

    # Batch complete
    job["status"] = "complete"
    total_defects = sum(r["stats"]["total_defects"] for r in job["results"])
    await sio.emit("detection_batch_complete", {
        "job_id": job_id,
        "total_files": len(job["results"]),
        "total_defects": total_defects,
    })


# ---------------------------------------------------------------------------
# Socket.IO events
# ---------------------------------------------------------------------------
@sio.event
async def connect(sid, environ):
    pass


@sio.event
async def subscribe_job(sid, data):
    job_id = data.get("job_id", "")
    if job_id:
        await sio.enter_room(sid, job_id)


@sio.event
async def disconnect(sid):
    pass


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.post("/api/uploads/batch/start")
async def batch_start(payload: dict):
    total = payload.get("total", 0)
    if total <= 0:
        raise HTTPException(400, "total must be > 0")

    confidence = payload.get("det_confidence", 0.25)
    slice_size = payload.get("det_slice_size", 640)
    overlap = payload.get("det_overlap", 0.2)
    source = payload.get("source", "rgb")

    job = _new_job(total, confidence, slice_size, overlap, source=source)

    # Pre-load model in background so first image is fast
    threading.Thread(target=get_model, daemon=True).start()

    # Start worker
    asyncio.create_task(_worker(job["job_id"]))

    return {"job_id": job["job_id"]}


@app.post("/api/uploads/file")
async def upload_file(job_id: str = Form(...), file: UploadFile = File(...)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    file_id = uuid.uuid4().hex[:10]
    img_bytes = await file.read()

    job["files"][file_id] = {
        "filename": file.filename or f"image_{file_id}.jpg",
        "status": "pending",
        "bytes": img_bytes,
    }
    # Auto-expand total when user adds more images to a running job
    job["total"] = max(job["total"], len(job["files"]))

    # Restart worker if job was already marked complete
    if job["status"] == "complete":
        job["status"] = "active"
        asyncio.create_task(_worker(job["job_id"]))

    await sio.emit("detection_queued", {
        "job_id": job_id,
        "file_id": file_id,
        "filename": file.filename,
    })

    return {"file_id": file_id, "status": "queued"}


@app.get("/api/detection/results/{job_id}")
async def get_results(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "total": job["total"],
        "completed": job["completed"],
        "results": job["results"],
    }


@app.get("/results/{job_id}/{filename}")
async def serve_result_file(job_id: str, filename: str):
    fpath = RESULTS_DIR / job_id / filename
    if not fpath.exists():
        raise HTTPException(404, "File not found")
    media = (
        "image/jpeg" if filename.endswith(".jpg")
        else "video/mp4" if filename.endswith(".mp4")
        else "application/octet-stream"
    )
    return FileResponse(str(fpath), media_type=media)


# ---------------------------------------------------------------------------
# Video processing — whole-video pipeline
# ---------------------------------------------------------------------------
video_jobs: dict[str, dict] = {}


def _get_ffmpeg_exe() -> str:
    """Get ffmpeg binary path from imageio_ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _reencode_to_h264(src: str, dst: str, fps: float) -> bool:
    """Re-encode mp4v to H.264 for browser playback. Try NVENC first, fallback to libx264."""
    import subprocess
    ffmpeg = _get_ffmpeg_exe()
    for encoder in ("h264_nvenc", "libx264"):
        cmd = [
            ffmpeg, "-y", "-i", src,
            "-c:v", encoder, "-preset", "fast",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-r", str(round(fps)),
            dst,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=600)
            if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
                print(f"[INFO] Re-encoded with {encoder}")
                return True
        except Exception:
            continue
    return False


def _batch_detect(model, frames: list[np.ndarray], confidence: float) -> list[list[dict]]:
    """Run YOLO on a batch of frames. imgsz=640, single GPU call."""
    results = model.predict(
        frames, conf=confidence, device=DEVICE,
        imgsz=640, verbose=False,
    )
    per_frame: list[list[dict]] = []
    for r in results:
        dets = []
        for box in r.boxes:
            cls_id = int(box.cls[0])
            dets.append({
                "bbox": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_id": cls_id,
                "class_name": model.names.get(cls_id, str(cls_id)),
            })
        per_frame.append(dets)
    return per_frame


def _process_whole_video(job_id: str, file_id: str, tmp_path: str,
                         confidence: float, slice_size: int, overlap: float,
                         frame_interval: float,
                         loop: asyncio.AbstractEventLoop) -> dict:
    """GPU-saturated video pipeline:
    - Reader thread keeps a 64-frame buffer ahead of GPU
    - Batched YOLO inference (16 frames/batch) with FP16 on cuda
    - Annotation pool (4 CPU threads) runs parallel to GPU
    - Writer thread handles disk I/O async
    - H.264 re-encode via NVENC for browser playback"""
    import torch

    cap = cv2.VideoCapture(tmp_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {tmp_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    duration = total_frames / fps if fps > 0 else 0

    out_dir = RESULTS_DIR / file_id
    out_dir.mkdir(exist_ok=True)
    raw_path = out_dir / "raw.mp4"
    writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    # Reader thread
    frame_q: queue.Queue = queue.Queue(maxsize=READ_AHEAD)
    read_done = threading.Event()
    def _reader():
        while True:
            ret, frm = cap.read()
            if not ret:
                break
            frame_q.put(frm)
        read_done.set()
    threading.Thread(target=_reader, daemon=True).start()

    # Writer thread
    write_q: queue.Queue = queue.Queue(maxsize=READ_AHEAD)
    def _writer_fn():
        while True:
            item = write_q.get()
            if item is None:
                break
            writer.write(item)
    writer_t = threading.Thread(target=_writer_fn, daemon=True)
    writer_t.start()

    model = get_model()
    all_det_count = 0
    conf_sum = 0.0
    max_conf = 0.0
    frames_done = 0
    thumb_saved = False

    t0 = time.time()

    while True:
        # Fill batch from reader queue
        batch: list[np.ndarray] = []
        while len(batch) < GPU_BATCH:
            try:
                batch.append(frame_q.get(timeout=0.2))
            except queue.Empty:
                if read_done.is_set():
                    break
        if not batch:
            break

        # GPU inference — single batch call, FP16
        per_frame_dets = _batch_detect(model, batch, confidence)

        # Annotate concurrently on CPU threads
        def _ann(pair):
            frm, dets = pair
            annotate_image(frm, dets, copy=False)
            return frm
        list(_annotate_pool.map(_ann, zip(batch, per_frame_dets)))

        # Push to writer + stats
        for i, (frame, dets) in enumerate(zip(batch, per_frame_dets)):
            write_q.put(frame)
            all_det_count += len(dets)
            for d in dets:
                c = d["confidence"]
                conf_sum += c
                if c > max_conf:
                    max_conf = c
            if not thumb_saved and w > 0 and h > 0:
                scale = min(480 / w, 480 / h, 1.0)
                t = cv2.resize(batch[0], (max(1, int(w * scale)), max(1, int(h * scale))))
                cv2.imwrite(str(out_dir / "thumb.jpg"), t, [cv2.IMWRITE_JPEG_QUALITY, 85])
                thumb_saved = True

        frames_done += len(batch)
        pct = min(95, int((frames_done / total_frames) * 100))
        asyncio.run_coroutine_threadsafe(
            sio.emit("video_progress", {
                "job_id": job_id, "file_id": file_id,
                "frames_done": frames_done, "total_frames": total_frames,
                "percent": pct,
            }),
            loop,
        )

    write_q.put(None)
    writer_t.join(timeout=60)
    writer.release()
    cap.release()

    if DEVICE != "cpu":
        torch.cuda.empty_cache()

    elapsed = time.time() - t0
    throughput = frames_done / elapsed if elapsed > 0 else 0
    print(f"[PERF] {file_id}: {frames_done}f / {elapsed:.1f}s = {throughput:.0f} FPS | {all_det_count} dets")

    # H.264 re-encode for browser
    h264_path = out_dir / "annotated.mp4"
    if not _reencode_to_h264(str(raw_path), str(h264_path), fps):
        shutil.move(str(raw_path), str(h264_path))
        print("[WARN] H.264 re-encode failed, serving raw mp4v")
    else:
        try:
            os.unlink(str(raw_path))
        except Exception:
            pass

    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    avg_conf = (conf_sum / all_det_count) if all_det_count > 0 else 0
    return {
        "total_frames": total_frames,
        "frames_analyzed": frames_done,
        "duration": round(duration, 2),
        "fps": round(fps, 2),
        "total_detections": all_det_count,
        "avg_confidence": round(avg_conf, 4),
        "max_confidence": round(max_conf, 4),
        "thumb_url": f"/results/{file_id}/thumb.jpg",
        "video_url": f"/results/{file_id}/annotated.mp4",
    }


async def _video_item_worker(job_id: str):
    """Process videos sequentially — GPU gets 100% of resources per video."""
    vjob = video_jobs.get(job_id)
    if not vjob:
        return

    loop = asyncio.get_event_loop()

    while True:
        pending = None
        for fid, fdata in list(vjob["files"].items()):
            if fdata["status"] == "pending":
                fdata["status"] = "processing"
                pending = (fid, fdata)
                break

        if pending is None:
            all_done = (
                len(vjob["files"]) >= vjob["total"]
                and all(f["status"] in ("done", "error") for f in vjob["files"].values())
            )
            if all_done:
                break
            await asyncio.sleep(0.3)
            if time.time() - vjob["created_at"] > 3600:
                break
            continue

        fid, fdata = pending
        await sio.emit("video_item_start", {
            "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
        })

        try:
            result = await loop.run_in_executor(
                None, _process_whole_video,
                job_id, fid, fdata["tmp_path"],
                vjob["confidence"], vjob["slice_size"], vjob["overlap"],
                vjob.get("frame_interval", 1),
                loop,
            )
            fdata["status"] = "done"
            fdata["result"] = result
            vjob["completed"] += 1
            await sio.emit("video_item_result", {
                "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
                "completed": vjob["completed"], "total": vjob["total"],
                **result,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            fdata["status"] = "error"
            fdata["result"] = {"error": str(e)}
            vjob["completed"] += 1
            await sio.emit("video_item_result", {
                "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
                "error": str(e),
                "completed": vjob["completed"], "total": vjob["total"],
            })

    vjob["status"] = "complete"
    total_dets = sum(f.get("result", {}).get("total_detections", 0) for f in vjob["files"].values())
    await sio.emit("video_batch_complete", {
        "job_id": job_id,
        "total_videos": len(vjob["files"]),
        "total_detections": total_dets,
    })


@app.post("/api/video/batch/start")
async def video_batch_start(payload: dict):
    total = payload.get("total", 0)
    if total <= 0:
        raise HTTPException(400, "total must be > 0")

    vid_id = uuid.uuid4().hex[:12]
    video_jobs[vid_id] = {
        "job_id": vid_id,
        "total": total,
        "completed": 0,
        "confidence": payload.get("det_confidence", 0.25),
        "slice_size": payload.get("det_slice_size", 640),
        "overlap": payload.get("det_overlap", 0.2),
        "frame_interval": payload.get("frame_interval", 1),
        "files": {},
        "status": "active",
        "created_at": time.time(),
    }

    threading.Thread(target=get_model, daemon=True).start()
    asyncio.create_task(_video_item_worker(vid_id))

    return {"job_id": vid_id}


@app.post("/api/video/upload")
async def video_upload(job_id: str = Form(...), file: UploadFile = File(...)):
    vjob = video_jobs.get(job_id)
    if not vjob:
        raise HTTPException(404, "Video job not found")

    import tempfile
    file_id = uuid.uuid4().hex[:10]
    video_bytes = await file.read()

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.write(video_bytes)
    tmp.close()

    vjob["files"][file_id] = {
        "filename": file.filename or f"video_{file_id}.mp4",
        "status": "pending",
        "tmp_path": tmp.name,
        "result": None,
    }
    vjob["total"] = max(vjob["total"], len(vjob["files"]))

    if vjob["status"] == "complete":
        vjob["status"] = "active"
        asyncio.create_task(_video_item_worker(vjob["job_id"]))

    await sio.emit("video_item_queued", {
        "job_id": job_id, "file_id": file_id, "filename": file.filename,
    })

    return {"file_id": file_id, "status": "queued"}


@app.get("/api/video/results/{vid_id}")
async def video_results(vid_id: str):
    vjob = video_jobs.get(vid_id)
    if not vjob:
        raise HTTPException(404, "Video job not found")
    results = []
    for fid, fdata in vjob["files"].items():
        r = {"file_id": fid, "filename": fdata["filename"], "status": fdata["status"]}
        if fdata.get("result"):
            r.update(fdata["result"])
        results.append(r)
    return {
        "job_id": vid_id,
        "status": vjob["status"],
        "total": vjob["total"],
        "completed": vjob["completed"],
        "results": results,
    }


# ---------------------------------------------------------------------------
# Unified runs endpoint — merges image + video jobs for the Runs table
# ---------------------------------------------------------------------------
_THERMAL_KEYWORDS = ("thermal", "therm", "flir", "ir_", "_ir.", "infrared", "lwir", "mwir", "hotspot")

def _is_thermal_file(filename: str) -> bool:
    fn = filename.lower()
    return any(k in fn for k in _THERMAL_KEYWORDS)


def _build_run_entry(jid, job, run_type):
    """Build a unified run entry dict compatible with the frontend Run type."""
    from datetime import datetime, timezone

    rgb_findings = 0
    thermal_findings = 0

    job_source = job.get("source", "")

    if run_type == "image":
        total_defects = sum(r.get("stats", {}).get("total_defects", 0) for r in job.get("results", []))
        confs = [r.get("stats", {}).get("avg_confidence", 0) for r in job.get("results", []) if r.get("stats", {}).get("avg_confidence", 0) > 0]
        avg_conf = float(np.mean(confs)) if confs else 0
        needs_review = sum(1 for r in job.get("results", []) if r.get("stats", {}).get("total_defects", 0) > 0)
        files_info = []
        for fid, fdata in job.get("files", {}).items():
            res = next((r for r in job.get("results", []) if r.get("file_id") == fid), None)
            fname = fdata.get("filename", "")
            dcount = (res.get("stats", {}).get("total_defects", 0)) if res else 0
            fsource = job_source if job_source else ("thermal" if _is_thermal_file(fname) else "rgb")
            if fsource == "thermal":
                thermal_findings += dcount
            else:
                rgb_findings += dcount
            files_info.append({
                "file_id": fid, "filename": fname,
                "source": fsource,
                "status": fdata.get("status", "pending"),
                "thumb_url": res.get("thumb_url") if res else None,
                "annotated_url": res.get("annotated_url") if res else None,
                "detections": res.get("detections", []) if res else [],
                "stats": res.get("stats") if res else None,
            })
    else:
        total_defects = 0
        confs = []
        needs_review = 0
        files_info = []
        for fid, fdata in job.get("files", {}).items():
            res = fdata.get("result") or {}
            d = res.get("total_detections", 0)
            total_defects += d
            fname = fdata.get("filename", "")
            fsource = job_source if job_source else ("thermal" if _is_thermal_file(fname) else "rgb")
            if fsource == "thermal":
                thermal_findings += d
            else:
                rgb_findings += d
            ac = res.get("avg_confidence", 0)
            if ac > 0:
                confs.append(ac)
            if d > 0:
                needs_review += 1
            files_info.append({
                "file_id": fid, "filename": fname,
                "source": fsource,
                "status": fdata.get("status", "pending"),
                "thumb_url": res.get("thumb_url"), "video_url": res.get("video_url"),
                "total_detections": d, "duration": res.get("duration", 0),
                "fps": res.get("fps", 0), "frames_analyzed": res.get("frames_analyzed", 0),
                "avg_confidence": ac, "max_confidence": res.get("max_confidence", 0),
            })
        avg_conf = float(np.mean(confs)) if confs else 0

    ts = job.get("created_at", 0)
    created_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

    raw_status = job.get("status", "active")
    n_files = len(job.get("files", {}))
    n_completed = job.get("completed", 0)
    if raw_status == "active" and n_files > 0 and n_completed >= n_files:
        raw_status = "complete"
        job["status"] = "complete"
    status_map = {"active": "processing", "complete": "completed"}
    return {
        "id": jid, "run_id": jid,
        "type": run_type,
        "status": status_map.get(raw_status, raw_status),
        "total_files": n_files,
        "completed": n_completed,
        "findings_count": total_defects,
        "total_defects": total_defects,
        "rgb_findings": rgb_findings,
        "thermal_findings": thermal_findings,
        "must_review_count": needs_review,
        "needs_review": needs_review,
        "avg_confidence": round(avg_conf, 4),
        "ai_confidence": round(avg_conf, 4),
        "created_at": created_iso,
        "timestamp": created_iso,
        "_created_ts": ts,
        "files": files_info,
    }


@app.get("/api/runs")
async def get_all_runs():
    """Return all image and video jobs as a flat array compatible with the Dashboard Run type."""
    result = []
    for jid, job in jobs.items():
        result.append(_build_run_entry(jid, job, "image"))
    for vid, vjob in video_jobs.items():
        result.append(_build_run_entry(vid, vjob, "video"))
    result.sort(key=lambda r: r.get("_created_ts", 0), reverse=True)
    return result


@app.get("/api/summary")
async def get_summary():
    """Dashboard summary stats built from actual upload data."""
    all_runs = []
    for jid, job in jobs.items():
        all_runs.append(_build_run_entry(jid, job, "image"))
    for vid, vjob in video_jobs.items():
        all_runs.append(_build_run_entry(vid, vjob, "video"))

    total_findings = sum(r["total_defects"] for r in all_runs)
    confs = [r["avg_confidence"] for r in all_runs if r["avg_confidence"] > 0]
    return {
        "towers_total": len(all_runs),
        "findings_total": total_findings,
        "avg_ai_confidence": round(float(np.mean(confs)), 4) if confs else 0,
        "status_counts": {
            "HEALTHY": sum(1 for r in all_runs if r["total_defects"] == 0 and r["status"] == "completed"),
            "MONITOR": sum(1 for r in all_runs if 0 < r["total_defects"] <= 5),
            "REQUIRES_INSPECTION": sum(1 for r in all_runs if r["total_defects"] > 5),
        },
    }


@app.get("/api/bulk-batches/latest")
async def bulk_latest():
    raise HTTPException(404, "No bulk batches")


@app.get("/api/bulk-batches/recent")
async def bulk_recent():
    return []


@app.get("/health")
async def health():
    gpu_name = "N/A"
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "ok": True,
        "model": str(WEIGHTS_PATH),
        "device": DEVICE,
        "gpu": gpu_name,
        "half_precision": USE_HALF,
        "service": "detection-server",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[INFO] Detection server starting on port 8000")
    print(f"[INFO] Weights: {WEIGHTS_PATH}")
    print(f"[INFO] Device: {DEVICE} | FP16: {USE_HALF}")
    print(f"[INFO] Results dir: {RESULTS_DIR}")
    threading.Thread(target=get_model, daemon=True).start()
    uvicorn.run(socket_app, host="0.0.0.0", port=8000, log_level="info")
