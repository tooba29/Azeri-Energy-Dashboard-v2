"""
In-memory job storage for image and video processing jobs.
"""

import time
import uuid
from datetime import datetime, timezone

import numpy as np

jobs: dict[str, dict] = {}
video_jobs: dict[str, dict] = {}
thermal_jobs: dict[str, dict] = {}

_THERMAL_KEYWORDS = ("thermal", "therm", "flir", "ir_", "_ir.", "infrared", "lwir", "mwir", "hotspot")


def new_job(total: int, confidence: float, slice_size: int, overlap: float, source: str = "rgb") -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "total": total,
        "confidence": confidence,
        "slice_size": slice_size,
        "overlap": overlap,
        "source": source,
        "files": {},
        "results": [],
        "completed": 0,
        "status": "active",
        "created_at": time.time(),
    }
    jobs[job_id] = job
    return job


def _is_thermal_file(filename: str) -> bool:
    fn = filename.lower()
    return any(k in fn for k in _THERMAL_KEYWORDS)


def build_run_entry(jid: str, job: dict, run_type: str) -> dict:
    """Build a unified run entry dict compatible with the frontend Run type."""
    rgb_findings = 0
    thermal_findings = 0
    job_source = job.get("source", "")

    if run_type == "image":
        total_defects = sum(
            r.get("stats", {}).get("total_defects", 0) for r in job.get("results", [])
        )
        confs = [
            r.get("stats", {}).get("avg_confidence", 0)
            for r in job.get("results", [])
            if r.get("stats", {}).get("avg_confidence", 0) > 0
        ]
        avg_conf = float(np.mean(confs)) if confs else 0
        needs_review = sum(
            1 for r in job.get("results", [])
            if r.get("stats", {}).get("total_defects", 0) > 0
        )
        files_info = []
        for fid, fdata in job.get("files", {}).items():
            res = next((r for r in job.get("results", []) if r.get("file_id") == fid), None)
            fname = fdata.get("filename", "")
            dcount = (res.get("stats", {}).get("total_defects", 0)) if res else 0
            fsource = job_source if job_source else ("thermal" if _is_thermal_file(fname) else "rgb")
            if fsource == "thermal":
                thermal_findings += dcount
            else:
                rgb_findings += dcount
            files_info.append({
                "file_id": fid, "filename": fname,
                "source": fsource,
                "status": fdata.get("status", "pending"),
                "thumb_url": res.get("thumb_url") if res else None,
                "annotated_url": res.get("annotated_url") if res else None,
                "detections": res.get("detections", []) if res else [],
                "stats": res.get("stats") if res else None,
            })
    else:
        total_defects = 0
        confs = []
        needs_review = 0
        files_info = []
        for fid, fdata in job.get("files", {}).items():
            res = fdata.get("result") or {}
            d = res.get("total_detections", 0)
            total_defects += d
            fname = fdata.get("filename", "")
            fsource = job_source if job_source else ("thermal" if _is_thermal_file(fname) else "rgb")
            if fsource == "thermal":
                thermal_findings += d
            else:
                rgb_findings += d
            ac = res.get("avg_confidence", 0)
            if ac > 0:
                confs.append(ac)
            if d > 0:
                needs_review += 1
            files_info.append({
                "file_id": fid, "filename": fname,
                "source": fsource,
                "status": fdata.get("status", "pending"),
                "thumb_url": res.get("thumb_url"), "video_url": res.get("video_url"),
                "total_detections": d, "duration": res.get("duration", 0),
                "fps": res.get("fps", 0), "frames_analyzed": res.get("frames_analyzed", 0),
                "avg_confidence": ac, "max_confidence": res.get("max_confidence", 0),
            })
        avg_conf = float(np.mean(confs)) if confs else 0

    ts = job.get("created_at", 0)
    created_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

    raw_status = job.get("status", "active")
    n_files = len(job.get("files", {}))
    n_completed = job.get("completed", 0)
    if raw_status == "active" and n_files > 0 and n_completed >= n_files:
        raw_status = "complete"
        job["status"] = "complete"
    status_map = {"active": "processing", "complete": "completed"}
    return {
        "id": jid, "run_id": jid,
        "type": run_type,
        "status": status_map.get(raw_status, raw_status),
        "total_files": n_files,
        "completed": n_completed,
        "findings_count": total_defects,
        "total_defects": total_defects,
        "rgb_findings": rgb_findings,
        "thermal_findings": thermal_findings,
        "must_review_count": needs_review,
        "needs_review": needs_review,
        "avg_confidence": round(avg_conf, 4),
        "ai_confidence": round(avg_conf, 4),
        "created_at": created_iso,
        "timestamp": created_iso,
        "_created_ts": ts,
        "files": files_info,
    }


# ---------------------------------------------------------------------------
# Thermal job helpers
# ---------------------------------------------------------------------------

def new_thermal_job(total: int, palette: int = 2, unit: str = "Celsius",
                    object_type: str | None = None) -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "total": total,
        "palette": palette,
        "unit": unit,
        "object_type": object_type,
        "files": {},
        "results": [],
        "completed": 0,
        "status": "active",
        "created_at": time.time(),
    }
    thermal_jobs[job_id] = job
    return job


def build_thermal_run_entry(jid: str, job: dict) -> dict:
    """Build a unified run entry for a thermal batch job."""
    n_files = len(job.get("files", {}))
    n_completed = job.get("completed", 0)
    results = job.get("results", [])

    files_info = []
    for fid, fdata in job.get("files", {}).items():
        res = next((r for r in results if r.get("file_id") == fid), None)
        files_info.append({
            "file_id": fid,
            "filename": fdata.get("filename", ""),
            "source": "thermal",
            "status": fdata.get("status", "pending"),
            "thumb_url": res.get("thermal_image_url") if res else None,
            "stats": res.get("stats") if res else None,
            "analysis": res.get("analysis") if res else None,
        })

    needs_review = sum(1 for r in results if r.get("stats"))

    ts = job.get("created_at", 0)
    created_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

    raw_status = job.get("status", "active")
    if raw_status == "active" and n_files > 0 and n_completed >= n_files:
        raw_status = "complete"
        job["status"] = "complete"
    status_map = {"active": "processing", "complete": "completed"}

    return {
        "id": jid, "run_id": jid,
        "type": "thermal",
        "status": status_map.get(raw_status, raw_status),
        "total_files": n_files,
        "completed": n_completed,
        "findings_count": n_completed,
        "total_defects": 0,
        "rgb_findings": 0,
        "thermal_findings": n_completed,
        "must_review_count": needs_review,
        "needs_review": needs_review,
        "avg_confidence": 0,
        "ai_confidence": 0,
        "created_at": created_iso,
        "timestamp": created_iso,
        "_created_ts": ts,
        "files": files_info,
    }
