"""
Unified runs, summary, health, bulk-batch, and static result-file controllers.
"""

import numpy as np
from fastapi import HTTPException

from backend.config import WEIGHTS_PATH, DEVICE, USE_HALF, RESULTS_DIR
from backend.services.job_store import jobs, video_jobs, thermal_jobs, build_run_entry, build_thermal_run_entry


async def get_all_runs() -> list:
    """Return all image, video, and thermal jobs as a flat array compatible with the Dashboard Run type."""
    result = []
    for jid, job in jobs.items():
        result.append(build_run_entry(jid, job, "image"))
    for vid, vjob in video_jobs.items():
        result.append(build_run_entry(vid, vjob, "video"))
    for tid, tjob in thermal_jobs.items():
        result.append(build_thermal_run_entry(tid, tjob))
    result.sort(key=lambda r: r.get("_created_ts", 0), reverse=True)
    return result


async def get_summary() -> dict:
    """Dashboard summary stats built from actual upload data."""
    all_runs = []
    for jid, job in jobs.items():
        all_runs.append(build_run_entry(jid, job, "image"))
    for vid, vjob in video_jobs.items():
        all_runs.append(build_run_entry(vid, vjob, "video"))
    for tid, tjob in thermal_jobs.items():
        all_runs.append(build_thermal_run_entry(tid, tjob))

    total_findings = sum(r["total_defects"] for r in all_runs)
    confs = [r["avg_confidence"] for r in all_runs if r["avg_confidence"] > 0]
    return {
        "towers_total": len(all_runs),
        "findings_total": total_findings,
        "avg_ai_confidence": round(float(np.mean(confs)), 4) if confs else 0,
        "status_counts": {
            "HEALTHY": sum(1 for r in all_runs if r["total_defects"] == 0 and r["status"] == "completed"),
            "MONITOR": sum(1 for r in all_runs if 0 < r["total_defects"] <= 5),
            "REQUIRES_INSPECTION": sum(1 for r in all_runs if r["total_defects"] > 5),
        },
    }


async def get_run_detail(run_id: str) -> dict:
    """Find a single run by ID across all job stores and return full detail."""
    if run_id in jobs:
        return build_run_entry(run_id, jobs[run_id], "image")
    if run_id in video_jobs:
        return build_run_entry(run_id, video_jobs[run_id], "video")
    if run_id in thermal_jobs:
        return build_thermal_run_entry(run_id, thermal_jobs[run_id])
    raise HTTPException(404, f"Run {run_id} not found")


async def bulk_latest():
    raise HTTPException(404, "No bulk batches")


async def bulk_recent():
    return []


async def health() -> dict:
    gpu_name = "N/A"
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "ok": True,
        "model": str(WEIGHTS_PATH),
        "device": DEVICE,
        "gpu": gpu_name,
        "half_precision": USE_HALF,
        "service": "detection-server",
    }


def serve_result_file(job_id: str, filename: str):
    """Resolve path + media type for a result file. Raises 404 if missing."""
    fpath = RESULTS_DIR / job_id / filename
    if not fpath.exists():
        raise HTTPException(404, "File not found")
    media = (
        "image/jpeg" if filename.endswith(".jpg")
        else "image/png" if filename.endswith(".png")
        else "video/mp4" if filename.endswith(".mp4")
        else "application/octet-stream"
    )
    return fpath, media
