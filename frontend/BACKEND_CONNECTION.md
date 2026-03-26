# Connecting Frontend to Your Backend

This frontend is configured to call **`http://localhost:8080`** by default.

## Your backend folder

Your API server lives here:

```
E:\Office Work\Azerenerji Project\NEW AZERJI\pl_powerline_ai
```

That project has `server.py` (FastAPI) with `/health`, `/api/runs`, `/api/runs/{id}`, overlays, etc.—aligned with this frontend.

## How to connect

1. **Start the backend** from your backend folder:

   ```powershell
   cd "E:\Office Work\Azerenerji Project\NEW AZERJI\pl_powerline_ai"
   pip install fastapi uvicorn
   $env:RUN_SINGLE = "ToobaxSagar_Version/test_results"
   uvicorn server:app --host 0.0.0.0 --port 8080
   ```

   - `RUN_SINGLE=ToobaxSagar_Version/test_results` makes the server serve that one run (your `dashboard_report.json` + overlays).
   - To serve multiple runs from a directory, set `RUNS_DIR` instead, e.g. `$env:RUNS_DIR = "outputs/runs"`.

2. **Start the frontend** from this project:

   ```powershell
   cd "e:\Office Work\Azerenerji Project\270122026\frontend_fixed"
   npm run dev
   ```

3. **Check the UI**: the header shows a green **“API healthy”** when the backend on port 8080 is reachable.

## If the backend runs on another host or port

Create a `.env` file in this frontend folder:

```env
VITE_API_BASE=http://your-machine:8080
```

Then restart `npm run dev`.
