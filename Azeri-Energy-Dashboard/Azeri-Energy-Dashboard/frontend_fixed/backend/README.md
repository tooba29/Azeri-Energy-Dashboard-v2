# Powerline Inspection Runs API (FastAPI)

Drop-in backend that serves runs from disk and streams artifacts with headers that match the frontend and [BACKEND_CONTRACT.md](../BACKEND_CONTRACT.md).

## Folder layout assumed

```
outputs/
  runs/
    <run_id>/
      run.json
      artifacts/
        overlay.jpg   (or .png)
        annotated.jpg (or .png)
        thermal.jpg   (or .png)
        report.pdf
```

## Failed runs: keep run.json always

To keep the UI stable, the pipeline should **always** write `run.json`, even when a run fails. For failed runs, use at least:

```json
{
  "run_id": "abc123",
  "tower_id": "T-001",
  "status": "failed",
  "created_at": "2025-01-27T12:00:00Z",
  "error": "Model inference timeout"
}
```

Optional: add `validation_errors: []` or similar for client display. The list and detail endpoints will then show failed runs with status and error instead of missing entries.

If your pipeline writes elsewhere or uses different filenames, edit `server.py`:

- **`RUNS_DIR`** – path to the parent of `<run_id>` folders  
  Examples:
  - `Path("outputs/runs")`
  - `Path("ToobaxSagar_Version/test_results/runs")`
  - `Path("/data/inspection/runs")`

- **`ARTIFACT_MAP`** – possible filenames per artifact type:

  ```python
  ARTIFACT_MAP = {
      "overlay":   ["overlay.jpg", "overlay.png"],
      "annotated": ["annotated.jpg", "annotated.png"],
      "thermal":   ["thermal.jpg", "thermal.png", "thermal_overlay.jpg", "thermal_overlay.png"],
      "report":    ["report.pdf"],
  }
  ```

## `run.json` shape

The list and detail endpoints read from `run.json`. Minimum useful shape:

```json
{
  "run_id": "abc123",
  "tower_id": "T-001",
  "status": "completed",
  "created_at": "2025-01-27T12:00:00Z",
  "completed_at": "2025-01-27T12:05:00Z",
  "summary": {
    "findings_count": 12,
    "must_review_count": 2,
    "avg_confidence": 0.89
  },
  "metadata": {
    "timestamp": "2025-01-27T12:00:00Z",
    "gps": { "lat": 40.4, "lng": 49.9 },
    "phase": "production",
    "ambient_c": 25
  },
  "detections": [
    {
      "component_type": "insulator",
      "bbox": [100, 200, 300, 400],
      "det_conf": 0.92,
      "defect_type": "crack",
      "defect_conf": 0.88,
      "thermal_flag": false,
      "severity": "HIGH",
      "status": "confirmed"
    }
  ]
}
```

For **list** (`GET /api/runs`), only `run_id`, `status`, `summary`, and `metadata.timestamp` (or `created_at`) are needed; the rest can be omitted or filled later. For **detail** (`GET /api/runs/:id`), include `detections` and `metadata` as above. Artifact URLs are filled by the server from `/api/runs/<run_id>/artifacts/<type>`.

## Run the server

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8080
```

Point the frontend at this API:

```bash
# .env or .env.local (frontend)
VITE_API_BASE=http://localhost:8080
```

## Environment variables (backend)

- **`CORS_ORIGINS`** (optional) – Comma-separated origins allowed by CORS. Default `*` for development. In production set to your real frontend URL(s), e.g. `https://app.example.com` or `http://localhost:5173,https://app.example.com`. Keeping `*` with `allow_credentials=True` is not recommended long-term.

## Mirror legacy runs into the runs layout

If your pipeline still writes legacy folders (e.g. `ToobaxSagar_Version/test_results/` with `dashboard_report.json` and `overlays/*.jpg`), use the mirror script so `/api/runs` populates without refactoring the pipeline:

1. Edit **`scripts/mirror_runs.py`** at the top:
   - **`LEGACY_PATH`** – exact path to your legacy run folder (or parent of run folders).
   - **`OUTPUT_RUNS_DIR`** – directory where run folders will be written (should match `RUNS_DIR` in `server.py`, e.g. `outputs/runs`).
   - **`RUN_STYLE`** – `"RUN_SINGLE"` if one folder = one run, or `"RUNS_DIR"` if the legacy path contains multiple run subfolders.
2. Run: `python scripts/mirror_runs.py`.
3. Start the backend with `RUNS_DIR` pointing at `OUTPUT_RUNS_DIR`. The Runs page will list mirrored runs.

You can run the script after each pipeline run, or on a schedule. When the pipeline later writes the new layout directly, you can stop using the mirror.

## Endpoints (match BACKEND_CONTRACT.md)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check; returns `{ok, version, time}` |
| GET | `/api/runs` | Lightweight list of runs (no detections) |
| GET | `/api/runs/:id` | Full run detail + artifact URLs |
| GET | `/api/runs/:id/artifacts/:type` | Stream overlay/report/annotated/thermal |
| GET | `/api/runs/:id/artifacts/overlays` | JSON list `[{ filename, url, tag, severity, stem }]` for overlay gallery |
| GET | `/api/runs/:id/artifacts/overlays/:filename` | Stream one overlay image |
| GET | `/api/runs/:id/artifacts/overlays.zip` | Stream zip of all overlays |

Artifact responses use `Content-Type` and `Cache-Control: public, max-age=86400, immutable`. Use `?download=true` to force `Content-Disposition: attachment`.

**Overlay list** (`GET /api/runs/:id/artifacts/overlays`) returns `[{ filename, url, tag, severity, stem }]` so the UI can filter/sort without parsing filenames:

- `tag` – first token of filename (e.g. `broken`, `rust`, `normal`). Unknown tags → `"unknown"`.
- `severity` – `HIGH` | `MEDIUM` | `LOW` from tag. Unknown/unclassified → `LOW` (not MEDIUM) so UI can show neutral.
- `stem` – middle part only; trailing `_overlay` is stripped, earlier segments are kept (e.g. `broken_insplad_det_284-2_DJI_0437_overlay.jpg` → stem `insplad_det_284-2_DJI_0437`).

## Customising to your layout

If you share:

1. The real path where runs are stored (e.g. `ToobaxSagar_Version/test_results/...`),
2. The actual artifact filenames (overlay, report, annotated, thermal),

then `RUNS_DIR` and `ARTIFACT_MAP` can be set to match your pipeline output exactly.
