"""
Single-image detection processing pipeline + async worker.
"""

import asyncio
import time

import cv2
import numpy as np

from backend.config import RESULTS_DIR
from backend.websockets.socket import sio
from backend.services.detection import run_sahi_detection, annotate_image
from backend.services.job_store import jobs


def process_file(
    job_id: str, file_id: str, img_bytes: bytes, filename: str,
    confidence: float, slice_size: int, overlap: float,
    loop: asyncio.AbstractEventLoop,
) -> dict:
    """Process one image: detect, annotate, save thumb+annotated, return result dict."""
    t0 = time.time()

    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"file_id": file_id, "filename": filename, "error": "Cannot decode image"}

    asyncio.run_coroutine_threadsafe(
        sio.emit("detection_start", {"job_id": job_id, "file_id": file_id, "filename": filename}),
        loop,
    )

    dets = run_sahi_detection(img, confidence, slice_size, overlap, job_id, file_id, loop)

    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    thumb_path = job_dir / f"{file_id}_thumb.jpg"
    h, w = img.shape[:2]
    scale = min(640 / w, 640 / h, 1.0)
    thumb = cv2.resize(img, (int(w * scale), int(h * scale)))
    cv2.imwrite(str(thumb_path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])

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


async def image_worker(job_id: str):
    """Process files as they arrive for this job."""
    job = jobs.get(job_id)
    if not job:
        return

    loop = asyncio.get_event_loop()

    while True:
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

            fdata.pop("bytes", None)

        except Exception as e:
            fdata["status"] = "error"
            job["completed"] += 1
            await sio.emit("detection_result", {
                "job_id": job_id, "file_id": fid, "filename": fdata["filename"],
                "error": str(e), "completed": job["completed"], "total": job["total"],
            })

    job["status"] = "complete"
    total_defects = sum(r["stats"]["total_defects"] for r in job["results"])
    await sio.emit("detection_batch_complete", {
        "job_id": job_id,
        "total_files": len(job["results"]),
        "total_defects": total_defects,
    })
