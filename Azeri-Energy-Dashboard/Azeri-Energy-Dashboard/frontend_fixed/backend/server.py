"""
Drop-in FastAPI backend for Powerline Inspection runs.
Serves /api/runs and /api/runs/:id from disk; streams artifacts with correct headers.
Matches BACKEND_CONTRACT.md (see repo root).
Overlay gallery: list/stream overlays from artifacts/overlays/ and overlays.zip.
"""
import io
import os
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pathlib import Path
import json
from datetime import datetime
from typing import Optional

app = FastAPI(title="Powerline Inspection Backend", version="1.0.0")

# CORS: needed when frontend (e.g. localhost:5173) calls backend (localhost:8080).
# Production: set CORS_ORIGINS to your real frontend domain(s), e.g. "https://app.example.com".
# Using allow_origins=["*"] with allow_credentials=True is not recommended long-term.
_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ——— Configure to match your output layout ———
# Default: outputs/runs/<run_id>/run.json + artifacts/ (+ artifacts/overlays/ for gallery)
RUNS_DIR = Path("outputs/runs")

# If using mirror_runs.py, point at the same folder as OUTPUT_RUNS_DIR, e.g.:
# RUNS_DIR = Path(r"e:\Office Work\Azerenerji Project\NEW AZERJI\pl_powerline_ai\outputs\runs")

# Map artifact type -> possible filenames (edit to match your pipeline outputs)
ARTIFACT_MAP = {
    "overlay": ["overlay.jpg", "overlay.png"],
    "annotated": ["annotated.jpg", "annotated.png"],
    "thermal": ["thermal.jpg", "thermal.png", "thermal_overlay.jpg", "thermal_overlay.png"],
    "report": ["report.pdf"],
}

CACHE_CONTROL = "public, max-age=86400, immutable"  # 1 day


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON: {p.name}: {e}")


def _run_path(run_id: str) -> Path:
    p = RUNS_DIR / run_id
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    return p


def _run_json(run_id: str) -> dict:
    rp = _run_path(run_id)
    jf = rp / "run.json"
    if not jf.exists():
        raise HTTPException(status_code=404, detail="run.json not found for run")
    return _read_json(jf)


def _guess_content_type(file_path: Path, artifact_type: str) -> str:
    if artifact_type == "report":
        return "application/pdf"
    ext = file_path.suffix.lower()
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def _find_artifact_file(run_id: str, artifact_type: str) -> Path:
    rp = _run_path(run_id)
    artifacts_dir = rp / "artifacts"
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="Artifacts folder not found")

    candidates = ARTIFACT_MAP.get(artifact_type)
    if not candidates:
        raise HTTPException(status_code=400, detail="Unknown artifact type")

    for name in candidates:
        fp = artifacts_dir / name
        if fp.exists():
            return fp

    raise HTTPException(status_code=404, detail="Artifact not found")


def _overlays_dir(run_id: str) -> Path:
    """artifacts/overlays/ for a run; 404 if missing."""
    rp = _run_path(run_id)
    d = rp / "artifacts" / "overlays"
    if not d.exists() or not d.is_dir():
        raise HTTPException(status_code=404, detail="Overlays folder not found")
    return d


def _safe_overlay_path(run_id: str, filename: str) -> Path:
    """Resolve filename under artifacts/overlays/; reject path traversal."""
    base = _overlays_dir(run_id)
    resolved = (base / filename).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Overlay file not found")
    return resolved


# Overlay filename parsing: tag = first token, severity = HIGH/MEDIUM/LOW, stem = middle (everything between tag and trailing _overlay)
_OVERLAY_TAG_TO_SEVERITY = {
    "broken": "HIGH",
    "missing_part": "HIGH",
    "pollution_flashover": "HIGH",
    "flashover": "HIGH",
    "rust": "MEDIUM",
    "damage": "MEDIUM",
    "normal": "LOW",
}


def _parse_overlay_filename(name: str) -> dict:
    """Return { tag, severity, stem } from overlay filename.
    Unknown tags → severity LOW and tag 'unknown' (unclassified, show neutral in UI).
    Stem = everything between first token and trailing _overlay only (e.g. broken_insplad_det_284-2_DJI_0437_overlay.jpg → insplad_det_284-2_DJI_0437).
    """
    base = name.rsplit(".", 1)[0] if "." in name else name
    parts = base.split("_")
    tag = (parts[0].lower() if parts else "") or "unknown"
    severity = _OVERLAY_TAG_TO_SEVERITY.get(tag, "LOW")  # unknown → LOW (unclassified), not MEDIUM
    # Stem: middle part(s) only; remove trailing "_overlay" suffix, never strip earlier segments
    rest = parts[1:] if len(parts) > 1 else []
    if rest and rest[-1].lower() == "overlay":
        rest = rest[:-1]
    stem = "_".join(rest) if rest else base
    return {"tag": tag, "severity": severity, "stem": stem}


@app.get("/health")
def health():
    """Fast health check; frontend prefers this over /api/summary."""
    return {"ok": True, "version": "1.0.0", "time": datetime.now().isoformat()}


@app.get("/api/runs")
def list_runs(limit: int = 200):
    """
    Lightweight Run[] list — no detections.
    Response shape matches BACKEND_CONTRACT.md (id, created_at, status, counts, etc.).
    """
    if not RUNS_DIR.exists():
        return []

    items = []
    run_dirs = sorted(
        [p for p in RUNS_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for p in run_dirs[: max(1, min(limit, 1000))]:
        run_id = p.name
        jf = p / "run.json"
        if not jf.exists():
            continue

        data = _read_json(jf)
        summary = data.get("summary", {})
        metadata = data.get("metadata", {})

        # Contract fields: id, created_at (required), run_id, status, completed_at, counts, ai_confidence, error
        ts = metadata.get("timestamp") or data.get("created_at") or datetime.fromtimestamp(jf.stat().st_mtime).isoformat()
        items.append({
            "id": data.get("run_id", run_id),
            "run_id": data.get("run_id", run_id),
            "tower_id": data.get("tower_id"),
            "status": data.get("status", "completed"),
            "created_at": ts if isinstance(ts, str) else (ts.isoformat() if hasattr(ts, "isoformat") else str(ts)),
            "completed_at": metadata.get("completed_at") or data.get("completed_at"),
            "findings_count": summary.get("findings_count"),
            "must_review_count": summary.get("must_review_count"),
            "ai_confidence": summary.get("avg_confidence") or summary.get("ai_confidence"),
            "error": data.get("error"),
        })

    return items


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """
    Full RunDetail — detections, artifact URLs, metadata.
    Ensures artifact URLs point to /api/runs/:id/artifacts/:type.
    """
    data = _run_json(run_id)

    # Ensure artifact URLs (contract expects URLs, not paths)
    artifacts = dict(data.get("artifacts") or {})
    base = f"/api/runs/{run_id}/artifacts"
    artifacts.setdefault("overlay_url", f"{base}/overlay")
    artifacts.setdefault("annotated_url", f"{base}/annotated")
    artifacts.setdefault("thermal_url", f"{base}/thermal")
    artifacts.setdefault("report_url", f"{base}/report")
    data["artifacts"] = artifacts

    # Ensure id/run_id for frontend
    data.setdefault("id", run_id)
    data.setdefault("run_id", run_id)

    return data


# Overlay gallery: list, single-file stream, and zip (declare before generic /artifacts/{type})
@app.get("/api/runs/{run_id}/artifacts/overlays.zip")
def get_overlays_zip(run_id: str):
    """Stream a zip of all files in artifacts/overlays/."""
    base = _overlays_dir(run_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(base.iterdir()):
            if f.is_file():
                zf.write(f, f.name)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Cache-Control": CACHE_CONTROL,
            "Content-Disposition": f'attachment; filename="overlays_{run_id}.zip"',
        },
    )


@app.get("/api/runs/{run_id}/artifacts/overlays")
def list_overlays(run_id: str):
    """Return JSON list of { filename, url, tag, severity, stem } for artifacts/overlays/."""
    base = _overlays_dir(run_id)
    prefix = f"/api/runs/{run_id}/artifacts/overlays"
    items = []
    for f in sorted(base.iterdir()):
        if not f.is_file():
            continue
        parsed = _parse_overlay_filename(f.name)
        items.append({
            "filename": f.name,
            "url": f"{prefix}/{f.name}",
            "tag": parsed["tag"],
            "severity": parsed["severity"],
            "stem": parsed["stem"],
        })
    return items


@app.get("/api/runs/{run_id}/artifacts/overlays/{filename:path}")
def get_overlay_file(run_id: str, filename: str, download: Optional[bool] = False):
    """Stream one overlay image from artifacts/overlays/{filename}."""
    if not filename or filename.strip() in ("", "."):
        raise HTTPException(status_code=404, detail="Overlay file not found")
    fp = _safe_overlay_path(run_id, filename.strip())
    ext = fp.suffix.lower()
    ctype = "image/png" if ext == ".png" else "image/jpeg"
    headers = {"Cache-Control": CACHE_CONTROL, "Content-Type": ctype}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{fp.name}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{fp.name}"'
    return FileResponse(path=str(fp), headers=headers)


@app.get("/api/runs/{run_id}/artifacts/{artifact_type}")
def get_artifact(run_id: str, artifact_type: str, download: Optional[bool] = False):
    """
    Stream artifact with Content-Type + Cache-Control per BACKEND_CONTRACT.md.
    ?download=true forces Content-Disposition: attachment.
    """
    fp = _find_artifact_file(run_id, artifact_type)
    ctype = _guess_content_type(fp, artifact_type)

    headers = {
        "Cache-Control": CACHE_CONTROL,
        "Content-Type": ctype,
    }
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{fp.name}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{fp.name}"'

    return FileResponse(path=str(fp), headers=headers)
