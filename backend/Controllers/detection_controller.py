"""
Image detection batch controller — orchestrates job creation, file uploads, and result retrieval.
"""

import asyncio
import threading
import uuid

from fastapi import UploadFile, HTTPException

from backend.services.job_store import jobs, new_job
from backend.services.model import get_model
from backend.services.image_processing import image_worker
from backend.websockets.socket import sio


async def start_batch(payload: dict) -> dict:
    total = payload.get("total", 0)
    if total <= 0:
        raise HTTPException(400, "total must be > 0")

    confidence = payload.get("det_confidence", 0.25)
    slice_size = payload.get("det_slice_size", 640)
    overlap = payload.get("det_overlap", 0.2)
    source = payload.get("source", "rgb")

    job = new_job(total, confidence, slice_size, overlap, source=source)

    threading.Thread(target=get_model, daemon=True).start()
    asyncio.create_task(image_worker(job["job_id"]))

    return {"job_id": job["job_id"]}


async def upload_file(job_id: str, file: UploadFile) -> dict:
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
    job["total"] = max(job["total"], len(job["files"]))

    if job["status"] == "complete":
        job["status"] = "active"
        asyncio.create_task(image_worker(job["job_id"]))

    await sio.emit("detection_queued", {
        "job_id": job_id,
        "file_id": file_id,
        "filename": file.filename,
    })

    return {"file_id": file_id, "status": "queued"}


async def get_results(job_id: str) -> dict:
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
