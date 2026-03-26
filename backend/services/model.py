"""
YOLO model loading — lazy, thread-safe, with GPU warmup.
"""

import threading

import numpy as np

from backend.config import WEIGHTS_PATH, DEVICE

_model = None
_model_lock = threading.Lock()
_sahi_det_model = None
_sahi_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from ultralytics import YOLO
                import torch
                print(f"[INFO] Loading YOLO model from {WEIGHTS_PATH} ...")
                _model = YOLO(str(WEIGHTS_PATH))
                if DEVICE != "cpu":
                    dev = torch.device(f"cuda:{DEVICE}")
                    _model.to(dev)
                    dummy = [np.zeros((640, 640, 3), dtype=np.uint8)] * 4
                    _model.predict(dummy, imgsz=640, device=DEVICE, verbose=False)
                    torch.cuda.synchronize()
                    vram_used = torch.cuda.memory_allocated(0) / (1024**3)
                    print(f"[GPU] Model pinned + warmed up | VRAM: {vram_used:.2f} GB")
                print(f"[INFO] Model loaded. {len(_model.names)} classes")
    return _model


def get_sahi_model(confidence: float = 0.25):
    """Cached SAHI AutoDetectionModel wrapper — avoids re-creating every call."""
    global _sahi_det_model
    sahi_device = f"cuda:{DEVICE}" if DEVICE != "cpu" else "cpu"
    if _sahi_det_model is None or abs(_sahi_det_model._confidence - confidence) > 0.001:
        with _sahi_lock:
            from sahi import AutoDetectionModel
            model = get_model()
            _sahi_det_model = AutoDetectionModel.from_pretrained(
                model_type="ultralytics",
                model=model,
                confidence_threshold=confidence,
                device=sahi_device,
            )
            _sahi_det_model._confidence = confidence
    return _sahi_det_model
