"""
Thermal image processing controller — analyze, visualize, ROI stats, CSV export.
"""

import base64
import io
from typing import Optional

import numpy as np
from fastapi import UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image

from backend.services import thermal_analyzer as ta
from backend.services import thermal_processor as tp


def _init_sdk_if_possible() -> tuple[bool, str]:
    if tp.is_initialized():
        return True, "SDK already initialized."
    return tp.init_sdk()


def _image_to_base64_png(arr: np.ndarray) -> str:
    img = Image.fromarray(arr.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _sanitize_analysis_response(result: dict) -> dict:
    cleaned = dict(result)
    cleaned.pop("warnings", None)
    dist = cleaned.get("distance_meters")
    if isinstance(dist, dict):
        dist = dict(dist)
        dist.pop("assumptions", None)
        cleaned["distance_meters"] = dist
    return cleaned


async def analyze_image(
    image: UploadFile,
    object_type: Optional[str] = None,
    real_world_size_meters: Optional[float] = None,
    object_pixel_size: Optional[float] = None,
) -> JSONResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    sdk_ok, _ = _init_sdk_if_possible()
    object_info = {
        "object_type": object_type or None,
        "real_world_size_meters": real_world_size_meters,
        "object_pixel_size": object_pixel_size,
    }
    result = ta.analyze(
        image_bytes,
        object_info=object_info,
        thermal_data_available=sdk_ok,
    )
    return JSONResponse(_sanitize_analysis_response(result))


async def thermal_visualization(
    image: UploadFile,
    palette: int = 2,
    unit: str = "Celsius",
) -> JSONResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    sdk_ok, sdk_msg = _init_sdk_if_possible()
    if not sdk_ok:
        raise HTTPException(status_code=503, detail=f"DJI SDK unavailable: {sdk_msg}")

    try:
        temp_map_c = tp.extract_temperature_map(image_bytes, dtype="float32")
        thermal_rgb = tp.render_thermal_image(image_bytes, palette=palette)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Thermal processing failed: {exc}") from exc

    temp_map = tp.convert_temp_map(temp_map_c, unit)
    stats = tp.get_temperature_stats(temp_map)

    return JSONResponse({
        "unit": unit,
        "shape": {"height": int(temp_map.shape[0]), "width": int(temp_map.shape[1])},
        "stats": stats,
        "thermal_image_base64_png": _image_to_base64_png(thermal_rgb),
        "temperature_map": temp_map.tolist(),
    })


async def roi_stats(
    image: UploadFile,
    x1: int, y1: int, x2: int, y2: int,
    unit: str = "Celsius",
) -> JSONResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    sdk_ok, sdk_msg = _init_sdk_if_possible()
    if not sdk_ok:
        raise HTTPException(status_code=503, detail=f"DJI SDK unavailable: {sdk_msg}")

    temp_map_c = tp.extract_temperature_map(image_bytes, dtype="float32")
    temp_map = tp.convert_temp_map(temp_map_c, unit)
    h, w = temp_map.shape
    if x1 < 0 or y1 < 0 or x2 > w or y2 > h or x2 <= x1 or y2 <= y1:
        raise HTTPException(status_code=400, detail="Invalid ROI coordinates.")

    stats = tp.get_roi_stats(temp_map, x1, y1, x2, y2)
    return JSONResponse({
        "unit": unit,
        "roi": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        "stats": stats,
    })


async def export_csv(
    image: UploadFile,
    unit: str = "Celsius",
) -> StreamingResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    sdk_ok, sdk_msg = _init_sdk_if_possible()
    if not sdk_ok:
        raise HTTPException(status_code=503, detail=f"DJI SDK unavailable: {sdk_msg}")

    temp_map_c = tp.extract_temperature_map(image_bytes, dtype="float32")
    temp_map = tp.convert_temp_map(temp_map_c, unit)
    h, w = temp_map.shape
    rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")

    import pandas as pd

    df = pd.DataFrame({
        "row": rows.flatten(),
        "col": cols.flatten(),
        f"temp_{unit.lower()}": temp_map.flatten(),
    })
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    filename = f"{(image.filename or 'thermal').rsplit('.', 1)[0]}_temperatures.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def thermal_health() -> dict:
    sdk_ok, sdk_msg = _init_sdk_if_possible()
    return {"ok": True, "sdk_initialized": sdk_ok, "sdk_message": sdk_msg}
