# Wind forecast accuracy portal (UK day-ahead desk)

Web app that shows, for each January-2026 day-ahead purchase decision:
1. the **latest wind forecast available at decision time** (default 09:00 UK on D-1, changeable in the UI), and
2. **how accurate** those forecasts are (MAE, RMSE, bias, error by day / hour of day / forecast horizon) plus a likely-range band.

Data: national wind only, from Elexon BMRS — actuals `FUELHH` (fuelType WIND), forecasts `WINDFOR`. Nothing else.

## How it works (the one rule)
For every half-hour of delivery day D, we take the forecast with the **latest `publishTime` that is ≤ decision time on D-1**
and compare it to the actual. No future information is used. Error = forecast − actual. "Decisions in January 2026" = decisions
on 1–31 Jan, i.e. delivery days 2 Jan – 1 Feb. All times UTC (= UK time in January).

## Files
```
backend/app/data.py       download + load Elexon data (cached to backend/data/*.json); SAMPLE_DATA=1 gives synthetic data
backend/app/analysis.py   decision-time forecast selection + metrics
backend/app/main.py       FastAPI: /api/config, /api/day, /api/summary, /api/horizon (+ serves the built UI)
backend/tests/            pytest (look-ahead check, metrics, endpoints)
frontend/src/App.jsx      the whole React UI (Recharts)
Dockerfile                builds UI, then runs API+UI in one container
heroku.yml                Heroku container deploy
```

## Run
**Docker (recommended)**
```
docker compose up --build        # http://localhost:8000
```
First request downloads the Jan-2026 data from Elexon (~1 min) and caches it. To pre-download (and commit the files so deployment never
depends on Elexon being up): `cd backend && pip install -r requirements.txt && python -m app.data`.

**Without Docker**
```
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```
Offline demo with fake data: `SAMPLE_DATA=1 uvicorn app.main:app`. Tests: `cd backend && python -m pytest`.

## Deploy (Heroku)
```
python -m app.data   # in backend/, then commit backend/data/*.json
heroku create && heroku stack:set container && git push heroku main
```
Live app: <ADD LINK HERE>


