"""
Global configuration: paths, constants, and GPU device selection.
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_MODEL_DIR = Path(__file__).parent / "models" / "tl_defect_cn1"
WEIGHTS_PATH = _MODEL_DIR / "weights" / "best.pt"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

GPU_BATCH = 16
READ_AHEAD = 64
ANNOTATE_THREADS = 4


def _select_device() -> str:
    import torch
    if torch.cuda.is_available():
        torch.cuda.init()
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"[GPU] {name} | {vram:.1f} GB VRAM | CUDA {torch.version.cuda}")
        torch.backends.cudnn.benchmark = True
        return "0"
    print("[WARN] CUDA not available, using CPU")
    return "cpu"


DEVICE = _select_device()
USE_HALF = DEVICE != "cpu"

annotate_pool = ThreadPoolExecutor(max_workers=ANNOTATE_THREADS, thread_name_prefix="ann")
