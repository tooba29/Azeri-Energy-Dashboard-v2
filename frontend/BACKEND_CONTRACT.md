# Backend API Contract for Powerline Inspection Frontend

This document defines the API contract the frontend expects. Implementing these five endpoints with the described request/response shapes will make the product feel “complete” end-to-end.

---

## Required Endpoints

### 1. `POST /api/pipeline/run`

Start a new inspection run (RGB + optional thermal).

**Request body:** (existing)

```json
{
  "tower_id": "optional-string",
  "rgb_base64": "data:image/...;base64,...",
  "thermal_base64": "optional",
  "ambient_c": 25,
  "voltage_kv": "330 kV",
  "tower_type": "suspension",
  "region": "Karabakh",
  "corridor_tag": "optional"
}
```

**Response (minimum):**

```json
{
  "run_id": "abc123",
  "status": "processing"
}
```

**Response (recommended for redirect):**

```json
{
  "run_id": "abc123",
  "tower_id": "T-001",
  "status": "processing"
}
```

The frontend redirects to `/runs/:run_id` when `run_id` is present; otherwise it uses `tower_id` and goes to `/towers/:tower_id`, or `/runs` if neither is set.

**Failed runs:** The pipeline should still write `run.json` when a run fails: set `status: "failed"` and `error: "<message>"`. Optional: `validation_errors: []`. This keeps the Runs list and RunDetail stable instead of missing entries.

---

### 2. `GET /api/runs`

Returns a **lightweight list** of runs. Do **not** include full detections here.

**Response:** `Run[]`

```json
[
  {
    "id": "abc123",
    "run_id": "abc123",
    "tower_id": "T-001",
    "status": "completed",
    "created_at": "2025-01-27T12:00:00Z",
    "completed_at": "2025-01-27T12:05:00Z",
    "findings_count": 12,
    "must_review_count": 2,
    "ai_confidence": 0.89,
    "error": null
  }
]
```

**Fields:**

| Field              | Type   | Required | Notes                                      |
|--------------------|--------|----------|--------------------------------------------|
| `id`               | string | yes      | Unique run identifier                      |
| `run_id`           | string | no       | Alias; frontend uses `run_id \|\| id`       |
| `tower_id`         | string | no       | Associated tower                            |
| `status`           | string | yes      | `pending` \| `processing` \| `completed` \| `failed` |
| `created_at`       | string | yes      | ISO 8601                                   |
| `completed_at`     | string | no       | ISO 8601                                   |
| `findings_count`   | number | no       | Total detections                           |
| `must_review_count`| number | no       | Low-confidence / needs manual review       |
| `ai_confidence`    | number | no       | 0–1; can use `avg_confidence` as alias     |
| `error`            | string | no       | Used when `status === "failed"`            |

Keep this list small and fast; full detections and artifact metadata belong in `GET /api/runs/:id`.

---

### 3. `GET /api/runs/:id`

Returns full run detail including detections and artifact **URLs**.

**Response:** `RunDetail` (extends `Run` with detections, artifacts, metadata)

```json
{
  "id": "abc123",
  "run_id": "abc123",
  "tower_id": "T-001",
  "status": "completed",
  "created_at": "2025-01-27T12:00:00Z",
  "completed_at": "2025-01-27T12:05:00Z",
  "findings_count": 12,
  "must_review_count": 2,
  "ai_confidence": 0.89,
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
  ],
  "artifacts": {
    "overlay_url": "/api/runs/abc123/artifacts/overlay",
    "report_url": "/api/runs/abc123/artifacts/report",
    "annotated_url": "/api/runs/abc123/artifacts/annotated",
    "thermal_url": "/api/runs/abc123/artifacts/thermal"
  },
  "metadata": {
    "gps": { "lat": 40.4, "lng": 49.9 },
    "timestamp": "2025-01-27T12:00:00Z",
    "phase": "production",
    "ambient_c": 25
  }
}
```

**Artifact URLs (recommended)**

Return **URLs**, not filesystem paths:

- `overlay_url` – detection overlay image
- `report_url` – PDF report
- `annotated_url` – annotated image
- `thermal_url` – thermal overlay (if applicable)

Use paths like `/api/runs/:id/artifacts/overlay` (or full URL). Benefits:

- Frontend does not depend on storage layout
- Backend can switch storage (local → S3/GCS) without changing the UI
- Access control stays on the server

**Do not return:** `"overlay_path": "outputs/run123/overlay.jpg"`  
**Do return:** `"overlay_url": "/api/runs/run123/artifacts/overlay"`

The frontend still supports legacy `*_path` / `*_image` / `*_overlay` fields and will build URLs via `/api/runs/:id/artifacts/:type` when `*_url` is missing.

**Detections**

| Field           | Type   | Required | Notes                          |
|-----------------|--------|----------|--------------------------------|
| `component_type`| string | yes      | e.g. insulator, cross-arm     |
| `bbox`          | [4]    | yes      | [x1, y1, x2, y2]               |
| `det_conf`      | number | yes      | 0–1                            |
| `defect_type`   | string | no       | e.g. crack, corrosion         |
| `defect_conf`   | number | no       | 0–1                            |
| `thermal_flag`  | bool   | no       | From thermal analysis         |
| `severity`      | string | yes      | `HIGH` \| `MEDIUM` \| `LOW`    |
| `status`        | string | yes      | `confirmed` \| `needs_review` \| `false_positive` |

---

### 4. `GET /api/runs/:id/artifacts/:type`

Streams the artifact file. Frontend uses this when you return URLs like `/api/runs/abc123/artifacts/overlay`.

**`:type`:** `overlay` | `report` | `annotated` | `thermal`

**Response:** Binary (image or PDF). Set headers as below so nginx and browsers behave predictably.

**Content-Type (required)**

| `:type`     | Content-Type              | Notes                    |
|-------------|---------------------------|--------------------------|
| `overlay`   | `image/jpeg` or `image/png` | Detection overlay image |
| `report`    | `application/pdf`         | PDF report               |
| `annotated` | `image/jpeg` or `image/png` | Annotated image         |
| `thermal`   | `image/jpeg` or `image/png` | Thermal overlay         |

**Cache-Control (recommended)**

Artifacts are immutable per run, so they can be cached:

- **Images** (`overlay`, `annotated`, `thermal`):  
  `Cache-Control: public, max-age=86400, immutable`  
  (1 day; or longer e.g. `max-age=604800` for 7 days if run outputs never change.)

- **PDF** (`report`):  
  `Cache-Control: public, max-age=86400, immutable`

This keeps repeat visits to Run Detail fast and reduces load on the backend. Nginx can also add caching in front if needed.

**Optional:** Set `Content-Disposition: inline` for in-browser display, or `Content-Disposition: attachment; filename="report.pdf"` to force download.

---

### 5. `GET /health`

Lightweight health check for the API health indicator.

**Response:**

```json
{
  "ok": true,
  "version": "1.0.0",
  "time": "2025-01-27T12:00:00Z"
}
```

- Must be **fast** (e.g. &lt; 100 ms).
- Frontend uses this first; if `/health` is missing or fails, it falls back to `GET /api/summary`.

---

## Summary Table

| Method | Path                            | Purpose                          |
|--------|----------------------------------|----------------------------------|
| POST   | `/api/pipeline/run`             | Start run → return `run_id`      |
| GET    | `/api/runs`                     | Light list of runs               |
| GET    | `/api/runs/:id`                 | Full run + detections + artifact URLs |
| GET    | `/api/runs/:id/artifacts/:type`  | Stream overlay/report/etc.        |
| GET    | `/health`                       | Fast health check                |

---

## Drop-in FastAPI backend (disk-based runs)

A ready-to-run backend that implements this contract for **outputs on disk only** lives in `backend/`:

- **`backend/server.py`** – FastAPI app: `/health`, `/api/runs`, `/api/runs/:id`, `/api/runs/:id/artifacts/:type`
- **`backend/requirements.txt`** – `fastapi`, `uvicorn`
- **`backend/README.md`** – how to run, how to set `RUNS_DIR` and `ARTIFACT_MAP` to your folder layout and artifact filenames

Run from repo root:

```bash
cd backend && pip install -r requirements.txt && uvicorn server:app --host 0.0.0.0 --port 8080
```

Set `VITE_API_BASE=http://localhost:8080` so the frontend talks to this API. If your runs live in a different path or use different artifact names, edit `RUNS_DIR` and `ARTIFACT_MAP` in `server.py` (see `backend/README.md`).

---

## Backend integration checklist

To get a drop-in spec tailored to your stack, share:

1. **Backend stack** – Python (FastAPI/Flask), Node/Express, other?
2. **Where run results are stored** – local folders, DB, both?
3. **Current backend folder structure** (or a zip) – so routes, DB schema, and file serving can be mapped to this contract.

With that, you can implement these five endpoints and have the frontend work against them with no guesswork.
