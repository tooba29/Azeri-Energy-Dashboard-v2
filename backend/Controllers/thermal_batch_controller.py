"""
Thermal batch processing controller — start batch, upload files, get results.
"""

import asyncio
import uuid

from fastapi import UploadFile, HTTPException

from backend.services.job_store import thermal_jobs, new_thermal_job
from backend.services.thermal_image_worker import thermal_image_worker
from backend.websockets.socket import sio


async def start_thermal_batch(payload: dict) -> dict:
    total = payload.get("total", 0)
    if total <= 0:
        raise HTTPException(400, "total must be > 0")

    palette = payload.get("palette", 2)
    unit = payload.get("unit", "Celsius")
    object_type = payload.get("object_type") or None

    job = new_thermal_job(total, palette, unit, object_type)
    asyncio.create_task(thermal_image_worker(job["job_id"]))

    return {"job_id": job["job_id"]}


async def upload_thermal_file(job_id: str, file: UploadFile) -> dict:
    job = thermal_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Thermal job not found")

    file_id = uuid.uuid4().hex[:10]
    img_bytes = await file.read()

    job["files"][file_id] = {
        "filename": file.filename or f"thermal_{file_id}.jpg",
        "status": "pending",
        "bytes": img_bytes,
    }
    job["total"] = max(job["total"], len(job["files"]))

    if job["status"] == "complete":
        job["status"] = "active"
        asyncio.create_task(thermal_image_worker(job["job_id"]))

    await sio.emit("thermal_queued", {
        "job_id": job_id,
        "file_id": file_id,
        "filename": file.filename,
    })

    return {"file_id": file_id, "status": "queued"}


async def get_thermal_results(job_id: str) -> dict:
    job = thermal_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Thermal job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "total": job["total"],
        "completed": job["completed"],
        "results": job["results"],
    }
