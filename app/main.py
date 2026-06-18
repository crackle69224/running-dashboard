import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import db
from app.fit_parser import parse_fit_file
from app.zones import ZONE_COLORS, MAX_HR

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Running Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

db.init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "max_hr": MAX_HR, "zone_colors": ZONE_COLORS})


@app.post("/api/upload")
async def upload_fit(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".fit"):
        raise HTTPException(400, "Only .fit files are supported")

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        run_summary, records = parse_fit_file(tmp_path, file.filename)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse FIT file: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not records:
        raise HTTPException(400, "No record data found in FIT file")

    run_id = db.insert_run(run_summary, records)
    return {"id": run_id, **run_summary}


@app.get("/api/runs")
def get_runs():
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    run["records"] = db.get_run_records(run_id)
    return run


@app.delete("/api/runs/{run_id}")
def remove_run(run_id: int):
    if not db.get_run(run_id):
        raise HTTPException(404, "Run not found")
    db.delete_run(run_id)
    return {"deleted": run_id}


@app.get("/api/trends")
def get_trends():
    runs = db.list_runs()
    runs_sorted = sorted(runs, key=lambda r: r["start_time"] or "")
    return {
        "labels": [r["start_time"] for r in runs_sorted],
        "avg_hr": [r["avg_hr"] for r in runs_sorted],
        "zone2_pct": [r["zone2_pct"] for r in runs_sorted],
        "distance_km": [r["distance_km"] for r in runs_sorted],
    }
