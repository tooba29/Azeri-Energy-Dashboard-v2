"""
Video detection batch controller — orchestrates video job creation, uploads, and result retrieval.
"""

import asyncio
import tempfile
import threading
import time
import uuid

from fastapi import UploadFile, HTTPException

from backend.services.job_store import video_jobs
from backend.services.model import get_model
from backend.services.video_processing import video_item_worker
from backend.websockets.socket import sio


async def start_video_batch(payload: dict) -> dict:
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
    asyncio.create_task(video_item_worker(vid_id))

    return {"job_id": vid_id}


async def upload_video(job_id: str, file: UploadFile) -> dict:
    vjob = video_jobs.get(job_id)
    if not vjob:
        raise HTTPException(404, "Video job not found")

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
        asyncio.create_task(video_item_worker(vjob["job_id"]))

    await sio.emit("video_item_queued", {
        "job_id": job_id, "file_id": file_id, "filename": file.filename,
    })

    return {"file_id": file_id, "status": "queued"}


async def get_video_results(vid_id: str) -> dict:
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
