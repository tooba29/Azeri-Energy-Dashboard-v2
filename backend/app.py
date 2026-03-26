"""
Detection backend server (port 8000).
Uses YOLO + SAHI sliced inference with the tl_defect_cn1 best.pt weights.

GPU pipeline: FP16, multi-scale inference (640+1280), batched, CUDA-pinned,
parallel video workers, threaded read/annotate/write architecture.
"""

import sys
import threading
from pathlib import Path

# Ensure the project root is on sys.path so `from backend.*` imports resolve
# regardless of whether we run `python backend/app.py` or `python -m backend.app`.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import socketio as socketio_lib
import uvicorn
from fastapi import FastAPI

from backend.config import WEIGHTS_PATH, DEVICE, USE_HALF, RESULTS_DIR
from backend.middleware.cors import setup_cors
from backend.utils.errors import register_error_handlers
from backend.websockets.socket import sio
from backend.api.detection_routes import router as detection_router
from backend.api.video_routes import router as video_router
from backend.api.runs_routes import router as runs_router
from backend.services.model import get_model

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(title="Detection Server")

setup_cors(app)
register_error_handlers(app)

app.include_router(detection_router)
app.include_router(video_router)
app.include_router(runs_router)

# ---------------------------------------------------------------------------
# Socket.IO ASGI wrapper
# ---------------------------------------------------------------------------
socket_app = socketio_lib.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[INFO] Detection server starting on port 8000")
    print(f"[INFO] Weights: {WEIGHTS_PATH}")
    print(f"[INFO] Device: {DEVICE} | FP16: {USE_HALF}")
    print(f"[INFO] Results dir: {RESULTS_DIR}")
    threading.Thread(target=get_model, daemon=True).start()
    uvicorn.run(socket_app, host="0.0.0.0", port=8000, ws="wsproto", log_level="info")
