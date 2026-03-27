from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from backend.Controllers.thermal_controller import (
    analyze_image,
    thermal_visualization,
    roi_stats,
    export_csv,
    thermal_health,
)

router = APIRouter(tags=["Thermal"])


@router.get("/api/thermal/health")
async def thermal_health_route():
    return await thermal_health()


@router.post("/api/thermal/analyze")
async def analyze_route(
    image: UploadFile = File(...),
    object_type: Optional[str] = Form(default=None),
    real_world_size_meters: Optional[float] = Form(default=None),
    object_pixel_size: Optional[float] = Form(default=None),
):
    return await analyze_image(image, object_type, real_world_size_meters, object_pixel_size)


@router.post("/api/thermal/visualization")
async def visualization_route(
    image: UploadFile = File(...),
    palette: int = Form(default=2),
    unit: str = Form(default="Celsius"),
):
    return await thermal_visualization(image, palette, unit)


@router.post("/api/thermal/roi")
async def roi_route(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    unit: str = Form(default="Celsius"),
):
    return await roi_stats(image, x1, y1, x2, y2, unit)


@router.post("/api/thermal/export/csv")
async def export_csv_route(
    image: UploadFile = File(...),
    unit: str = Form(default="Celsius"),
):
    return await export_csv(image, unit)
