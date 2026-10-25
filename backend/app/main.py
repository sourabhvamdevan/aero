from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analysis

app = FastAPI(title="Wind forecast accuracy API")


@app.get("/api/config")
def get_config():
    return analysis.config()


@app.get("/api/day")
def get_day(date: date, decision_hour: int = Query(9, ge=0, le=23)):
    if date.isoformat() not in analysis.config()["delivery_days"]:
        raise HTTPException(404, "Date outside the Jan-2026 decision window")
    return analysis.day_view(date, decision_hour)


@app.get("/api/summary")
def get_summary(decision_hour: int = Query(9, ge=0, le=23)):
    return analysis.summary(decision_hour)


@app.get("/api/horizon")
def get_horizon():
    return analysis.horizon_view()


# Serve the built React app (present inside the Docker image)
DIST = Path(__file__).resolve().parent.parent / "static"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(DIST / "index.html")
