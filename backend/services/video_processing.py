"""
GPU-saturated video detection pipeline with threaded read/annotate/write.
"""

import asyncio
import os
import queue
import shutil
import threading
import time

import cv2
import numpy as np

from backend.config import RESULTS_DIR, DEVICE, GPU_BATCH, READ_AHEAD, annotate_pool
from backend.websockets.socket import sio
from backend.services.model import get_model
from backend.services.detection import annotate_image, batch_detect
from backend.services.job_store import video_jobs


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


def process_whole_video(
    job_id: str, file_id: str, tmp_path: str,
    confidence: float, slice_size: int, overlap: float,
    frame_interval: float,
    loop: asyncio.AbstractEventLoop,
) -> dict:
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
        batch: list[np.ndarray] = []
        while len(batch) < GPU_BATCH:
            try:
                batch.append(frame_q.get(timeout=0.2))
            except queue.Empty:
                if read_done.is_set():
                    break
        if not batch:
            break

        per_frame_dets = batch_detect(model, batch, confidence)

        def _ann(pair):
            frm, dets = pair
            annotate_image(frm, dets, copy=False)
            return frm
        list(annotate_pool.map(_ann, zip(batch, per_frame_dets)))

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


async def video_item_worker(job_id: str):
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
                None, process_whole_video,
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
