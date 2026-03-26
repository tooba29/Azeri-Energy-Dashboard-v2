"""
Detection logic: SAHI sliced inference, NMS merge, and image annotation.
"""

import asyncio
from typing import Optional

import cv2
import numpy as np

from backend.config import DEVICE
from backend.services.model import get_model, get_sahi_model
from backend.websockets.socket import sio

COLORS = [
    (0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 255, 0),
    (255, 128, 0), (128, 0, 255), (0, 128, 255), (255, 0, 128),
]


def run_sahi_detection(
    img: np.ndarray,
    confidence: float = 0.25,
    slice_size: int = 640,
    overlap: float = 0.2,
    job_id: str = "",
    file_id: str = "",
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> list[dict]:
    """Run YOLO + SAHI on a single image. Returns list[Detection]."""
    from sahi.predict import get_sliced_prediction

    model = get_model()
    detection_model = get_sahi_model(confidence)

    def _emit_progress(current: int, total_steps: int, pct: int):
        if loop and job_id:
            asyncio.run_coroutine_threadsafe(
                sio.emit("detection_progress", {
                    "job_id": job_id,
                    "file_id": file_id,
                    "current": current,
                    "total_steps": total_steps,
                    "percent": pct,
                }),
                loop,
            )

    # Full-image prediction on GPU
    _emit_progress(0, 2, 5)
    full_results = model.predict(img, conf=confidence, device=DEVICE, verbose=False)
    full_dets = []
    for r in full_results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            full_dets.append({
                "bbox": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_id": cls_id,
                "class_name": model.names.get(cls_id, str(cls_id)),
                "source": "full",
            })
    _emit_progress(1, 2, 40)

    # SAHI sliced prediction
    sahi_result = get_sliced_prediction(
        img,
        detection_model,
        slice_height=slice_size,
        slice_width=slice_size,
        overlap_height_ratio=overlap,
        overlap_width_ratio=overlap,
        verbose=0,
    )
    _emit_progress(2, 2, 85)

    sahi_dets = []
    for pred in sahi_result.object_prediction_list:
        bbox = pred.bbox.to_xyxy()
        sahi_dets.append({
            "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
            "confidence": float(pred.score.value),
            "class_id": int(pred.category.id),
            "class_name": pred.category.name,
            "source": "sahi",
        })

    all_dets = full_dets + sahi_dets
    if len(all_dets) > 0:
        all_dets = _nms_merge(all_dets, iou_threshold=0.5)

    return all_dets


def _nms_merge(dets: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Simple NMS merge across detections from different sources."""
    if not dets:
        return dets

    boxes = np.array([d["bbox"] for d in dets], dtype=np.float32)
    scores = np.array([d["confidence"] for d in dets], dtype=np.float32)

    indices = cv2.dnn.NMSBoxes(
        bboxes=[[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in boxes],
        scores=scores.tolist(),
        score_threshold=0.01,
        nms_threshold=iou_threshold,
    )
    if len(indices) == 0:
        return []
    keep = indices.flatten().tolist()
    return [dets[i] for i in keep]


def annotate_image(img: np.ndarray, dets: list[dict], copy: bool = True) -> np.ndarray:
    """Draw bounding boxes. Set copy=False for video frames (faster, in-place)."""
    canvas = img.copy() if copy else img
    for det in dets:
        x1, y1, x2, y2 = int(det["bbox"][0]), int(det["bbox"][1]), int(det["bbox"][2]), int(det["bbox"][3])
        cls_id = det.get("class_id", 0)
        color = COLORS[cls_id % len(COLORS)]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f'{det["class_name"]} {det["confidence"]:.0%}'
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(canvas, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(canvas, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return canvas


def batch_detect(model, frames: list[np.ndarray], confidence: float) -> list[list[dict]]:
    """Run YOLO on a batch of frames. imgsz=640, single GPU call."""
    results = model.predict(
        frames, conf=confidence, device=DEVICE,
        imgsz=640, verbose=False,
    )
    per_frame: list[list[dict]] = []
    for r in results:
        dets = []
        for box in r.boxes:
            cls_id = int(box.cls[0])
            dets.append({
                "bbox": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_id": cls_id,
                "class_name": model.names.get(cls_id, str(cls_id)),
            })
        per_frame.append(dets)
    return per_frame
