#!/usr/bin/env python3
"""
Mirror legacy run outputs into the runs convention so /api/runs populates.

Usage:
  1. Set LEGACY_PATH and OUTPUT_RUNS_DIR (and RUN_STYLE) below.
  2. Run:  python scripts/mirror_runs.py

Legacy layout assumed (customize in adapter if yours differs):
  <legacy_folder>/
    dashboard_report.json
    overlays/
      severity_*_overlay.jpg   (or similar)

New layout written:
  <OUTPUT_RUNS_DIR>/<run_id>/
    run.json
    artifacts/
      overlay.jpg
      overlays/   (optional: all legacy overlays copied here)
"""
from pathlib import Path
import json
import shutil
from datetime import datetime
from typing import Any

# ——— Paste your paths here ———
# Example (RUN_SINGLE = one run folder):
#   LEGACY_PATH = Path(r"e:\Office Work\Azerenerji Project\NEW AZERJI\pl_powerline_ai\ToobaxSagar_Version\test_results")
#   OUTPUT_RUNS_DIR = Path(r"e:\Office Work\Azerenerji Project\NEW AZERJI\pl_powerline_ai\outputs\runs")
LEGACY_PATH = Path("ToobaxSagar_Version/test_results")
OUTPUT_RUNS_DIR = Path("outputs/runs")

# "RUN_SINGLE" = LEGACY_PATH is one run folder (e.g. test_results with one dashboard_report.json)
# "RUNS_DIR"   = LEGACY_PATH contains multiple run folders; each subfolder = one run
RUN_STYLE = "RUN_SINGLE"  # or "RUNS_DIR"

# Legacy filenames (edit if your pipeline uses different names)
LEGACY_REPORT = "dashboard_report.json"
LEGACY_OVERLAYS_DIR = "overlays"
LEGACY_OVERLAY_GLOB = "*.jpg"  # or "severity_*_overlay.jpg", "*.png", etc.


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _adapter_legacy_to_run(legacy: dict, run_id: str, legacy_folder: Path) -> dict:
    """
    Convert legacy dashboard_report.json (or similar) into run.json schema.
    Customize this to match your real legacy fields.
    """
    # Example mapping; adjust keys to your actual dashboard_report / infer output shape
    detections = []
    for item in legacy.get("detections", legacy.get("findings", legacy.get("results", []))):
        # Normalize to contract shape: component_type, bbox, det_conf, defect_type, defect_conf, thermal_flag, severity, status
        bbox = item.get("bbox", item.get("bbox_xyxy", [0, 0, 0, 0]))
        if len(bbox) != 4:
            bbox = [0, 0, 0, 0]
        detections.append({
            "component_type": item.get("component_type", item.get("component", item.get("type", "unknown"))),
            "bbox": bbox,
            "det_conf": float(item.get("det_conf", item.get("confidence", item.get("conf", 0)))),
            "defect_type": item.get("defect_type", item.get("defect", "")),
            "defect_conf": float(item.get("defect_conf", item.get("defect_confidence", 0) or 0)),
            "thermal_flag": bool(item.get("thermal_flag", item.get("thermal", False))),
            "severity": (
                "HIGH" if (str(item.get("severity", "")).upper().startswith("H"))
                else "LOW" if (str(item.get("severity", "")).upper().startswith("L"))
                else "MEDIUM"
            ),
            "status": (
                "confirmed" if (str(item.get("status", "")).lower() in ("confirmed", "accept"))
                else "false_positive" if (str(item.get("status", "")).lower() in ("false_positive", "reject"))
                else "needs_review"
            ),
        })

    summary = legacy.get("summary", {})
    if not summary and detections:
        high = sum(1 for d in detections if (d.get("severity") or "").upper() == "HIGH")
        summary = {
            "findings_count": len(detections),
            "must_review_count": sum(1 for d in detections if (d.get("det_conf") or 0) < 0.7),
            "avg_confidence": sum(d.get("det_conf", 0) for d in detections) / len(detections) if detections else 0,
        }

    ts = legacy.get("timestamp", legacy.get("created_at", datetime.now().isoformat()))
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()

    return {
        "run_id": run_id,
        "tower_id": legacy.get("tower_id", legacy.get("tower", "")),
        "status": legacy.get("status", "completed"),
        "created_at": ts,
        "completed_at": legacy.get("completed_at", ts),
        "summary": {
            "findings_count": summary.get("findings_count", len(detections)),
            "must_review_count": summary.get("must_review_count", 0),
            "avg_confidence": summary.get("avg_confidence", 0),
        },
        "metadata": {
            "timestamp": ts,
            "gps": legacy.get("gps", legacy.get("metadata", {}).get("gps")),
            "phase": legacy.get("phase", "production"),
            "ambient_c": legacy.get("ambient_c"),
        },
        "detections": detections,
        "artifacts": {
            "overlay_url": f"/api/runs/{run_id}/artifacts/overlay",
            "report_url": f"/api/runs/{run_id}/artifacts/report",
            "annotated_url": f"/api/runs/{run_id}/artifacts/annotated",
            "thermal_url": f"/api/runs/{run_id}/artifacts/thermal",
        },
    }


# Severity order for "best" preview: HIGH first, then MEDIUM, then LOW, else first file.
# If your filenames use tokens like broken/rust/normal instead of HIGH/MEDIUM/LOW, they are mapped here.
_SEVERITY_ORDER = ("HIGH", "MEDIUM", "LOW")
_FIRST_TOKEN_TO_SEVERITY = {
    "broken": 0,
    "missing_part": 0,
    "flashover": 0,
    "high": 0,
    "medium": 1,
    "low": 2,
    "rust": 1,
    "normal": 2,
}


def _severity_rank(name: str) -> int:
    """Lower = higher priority. 0=HIGH, 1=MEDIUM, 2=LOW, 3=unknown."""
    first = name.split("_")[0].lower() if name else ""
    if first in _FIRST_TOKEN_TO_SEVERITY:
        return _FIRST_TOKEN_TO_SEVERITY[first]
    for i, s in enumerate(_SEVERITY_ORDER):
        if s.lower() in name.lower() or first == s.lower():
            return i
    return 3


def _pick_best_overlay(overlays_dir: Path, glob: str) -> Path | None:
    """Pick best overlay for UI preview: HIGH > MEDIUM > LOW (or broken/rust/normal mapping), else first file."""
    if not overlays_dir.exists():
        return None
    files = list(overlays_dir.glob(glob))
    if not files:
        return None
    best = min(files, key=lambda p: (_severity_rank(p.name), p.name))
    return best


def mirror_one(legacy_folder: Path, run_id: str, out_base: Path) -> None:
    report_path = legacy_folder / LEGACY_REPORT
    if not report_path.exists():
        print(f"  Skip {legacy_folder}: no {LEGACY_REPORT}")
        return

    legacy = json.loads(report_path.read_text(encoding="utf-8"))
    run_data = _adapter_legacy_to_run(legacy, run_id, legacy_folder)

    out_run = out_base / run_id
    artifacts_dir = _ensure_dir(out_run / "artifacts")

    # run.json
    (out_run / "run.json").write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    # Primary overlay for UI (best overlay → artifacts/overlay.jpg)
    overlays_src = legacy_folder / LEGACY_OVERLAYS_DIR
    best = _pick_best_overlay(overlays_src, LEGACY_OVERLAY_GLOB)
    if best:
        dest = artifacts_dir / "overlay.jpg"
        shutil.copy2(best, dest)
        print(f"  overlay: {best.name} -> {dest.relative_to(out_base)}")

    # Optional: copy all overlays into artifacts/overlays/
    if overlays_src.exists():
        overlays_dst = _ensure_dir(artifacts_dir / "overlays")
        for f in overlays_src.glob(LEGACY_OVERLAY_GLOB):
            shutil.copy2(f, overlays_dst / f.name)
        print(f"  overlays: {len(list(overlays_src.glob(LEGACY_OVERLAY_GLOB)))} files -> artifacts/overlays/")

    # Copy report.pdf if present
    for name in ("report.pdf", "dashboard_report.pdf", "report.pdf"):
        src = legacy_folder / name
        if src.exists():
            shutil.copy2(src, artifacts_dir / "report.pdf")
            print(f"  report: {name} -> artifacts/report.pdf")
            break

    print(f"  run.json written -> {out_run.relative_to(out_base)}")


def main() -> None:
    legacy = Path(LEGACY_PATH).resolve()
    out_base = Path(OUTPUT_RUNS_DIR).resolve()
    if not legacy.exists():
        print(f"Legacy path does not exist: {legacy}")
        print("Edit LEGACY_PATH at the top of this script.")
        return

    _ensure_dir(out_base)

    if RUN_STYLE == "RUN_SINGLE":
        run_id = legacy.name or "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"RUN_SINGLE: mirroring {legacy} -> run_id={run_id}")
        mirror_one(legacy, run_id, out_base)
    else:
        print(f"RUNS_DIR: mirroring subfolders of {legacy}")
        for sub in sorted(legacy.iterdir()):
            if sub.is_dir():
                run_id = sub.name
                print(f"  Run: {run_id}")
                mirror_one(sub, run_id, out_base)

    print(f"Done. Backend RUNS_DIR should be: {out_base}")


if __name__ == "__main__":
    main()
