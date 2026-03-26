from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.Controllers.runs_controller import (
    get_all_runs,
    get_summary,
    bulk_latest,
    bulk_recent,
    health,
    serve_result_file,
)

router = APIRouter(tags=["Runs & Dashboard"])


@router.get("/api/runs")
async def runs_route():
    return await get_all_runs()


@router.get("/api/summary")
async def summary_route():
    return await get_summary()


@router.get("/api/bulk-batches/latest")
async def bulk_latest_route():
    return await bulk_latest()


@router.get("/api/bulk-batches/recent")
async def bulk_recent_route():
    return await bulk_recent()


@router.get("/health")
async def health_route():
    return await health()


@router.get("/results/{job_id}/{filename}")
async def result_file_route(job_id: str, filename: str):
    fpath, media = serve_result_file(job_id, filename)
    return FileResponse(str(fpath), media_type=media)
