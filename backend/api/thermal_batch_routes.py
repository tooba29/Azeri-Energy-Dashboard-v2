from fastapi import APIRouter, UploadFile, File, Form

from backend.Controllers.thermal_batch_controller import (
    start_thermal_batch,
    upload_thermal_file,
    get_thermal_results,
)

router = APIRouter(tags=["Thermal Batch"])


@router.post("/api/thermal/batch/start")
async def thermal_batch_start_route(payload: dict):
    return await start_thermal_batch(payload)


@router.post("/api/thermal/batch/file")
async def thermal_batch_file_route(
    job_id: str = Form(...),
    file: UploadFile = File(...),
):
    return await upload_thermal_file(job_id, file)


@router.get("/api/thermal/batch/results/{job_id}")
async def thermal_batch_results_route(job_id: str):
    return await get_thermal_results(job_id)
