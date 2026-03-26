from fastapi import APIRouter, UploadFile, File, Form

from backend.Controllers.detection_controller import start_batch, upload_file, get_results

router = APIRouter(tags=["Detection"])


@router.post("/api/uploads/batch/start")
async def batch_start_route(payload: dict):
    return await start_batch(payload)


@router.post("/api/uploads/file")
async def upload_file_route(job_id: str = Form(...), file: UploadFile = File(...)):
    return await upload_file(job_id, file)


@router.get("/api/detection/results/{job_id}")
async def get_results_route(job_id: str):
    return await get_results(job_id)
