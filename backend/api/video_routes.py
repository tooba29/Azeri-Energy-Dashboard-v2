from fastapi import APIRouter, UploadFile, File, Form

from backend.Controllers.video_controller import start_video_batch, upload_video, get_video_results

router = APIRouter(tags=["Video"])


@router.post("/api/video/batch/start")
async def video_batch_start_route(payload: dict):
    return await start_video_batch(payload)


@router.post("/api/video/upload")
async def video_upload_route(job_id: str = Form(...), file: UploadFile = File(...)):
    return await upload_video(job_id, file)


@router.get("/api/video/results/{vid_id}")
async def video_results_route(vid_id: str):
    return await get_video_results(vid_id)
