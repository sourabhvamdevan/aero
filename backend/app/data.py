"""Loads wind actuals (FUELHH) and wind forecasts (WINDFOR) from Elexon.

Data is downloaded once, saved as JSON in backend/data/, and re-used afterwards.
Set SAMPLE_DATA=1 to use synthetic data (offline demo / tests).
Run `python -m app.data` to (re)download the real data.
"""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))

# Decisions are made during January 2026 (Jan 1..Jan 31) for delivery on the next day.
FIRST_DELIVERY = date(2026, 1, 2)
LAST_DELIVERY = date(2026, 2, 1)
UTC = timezone.utc


def _get(url, params):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=90)
            r.raise_for_status()
            body = r.json()
            return body["data"] if isinstance(body, dict) else body
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def _fetch_split(call, start, end, min_span):
    """Call API for [start, end]; if it fails, split the window in half and retry."""
    try:
        return call(start, end)
    except Exception:
        if end - start <= min_span:
            raise
        mid = start + (end - start) / 2
        return _fetch_split(call, start, mid, min_span) + _fetch_split(call, mid, end, min_span)


def fetch_actuals():
    def call(a, b):
        return _get(f"{BASE}/FUELHH/stream", {
            "settlementDateFrom": a.strftime("%Y-%m-%d"),
            "settlementDateTo": b.strftime("%Y-%m-%d"),
            "fuelType": "WIND",
        })
    rows, d = [], datetime.combine(FIRST_DELIVERY, datetime.min.time(), UTC)
    last = datetime.combine(LAST_DELIVERY, datetime.min.time(), UTC)
    while d <= last:
        end = min(d + timedelta(days=3), last)
        rows += _fetch_split(call, d, end, timedelta(days=1))
        d = end + timedelta(days=1)
    return [r for r in rows if r.get("fuelType") == "WIND"]


def fetch_forecasts():
    def call(a, b):
        return _get(f"{BASE}/WINDFOR/stream", {
            "publishDateTimeFrom": a.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    rows, d = [], datetime(2025, 12, 30, tzinfo=UTC)
    last = datetime(2026, 2, 1, tzinfo=UTC)
    while d < last:
        end = min(d + timedelta(days=2), last)
        rows += _fetch_split(call, d, end, timedelta(hours=6))
        d = end
    return rows


def download_all():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "actuals.json").write_text(json.dumps(fetch_actuals()))
    (DATA_DIR / "forecasts.json").write_text(json.dumps(fetch_forecasts()))
    load_actuals.cache_clear()
    load_forecasts.cache_clear()


def _sample():
    """Synthetic data shaped like the real thing, for offline use."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2025-12-29", "2026-02-02", freq="30min", tz="UTC")
    base = 9000 + 5000 * np.sin(np.arange(len(idx)) / 120) + np.cumsum(rng.normal(0, 60, len(idx)))
    truth = pd.Series(np.clip(base, 300, 20000), index=idx)
    act = pd.DataFrame({"startTime": idx, "actual": truth.values})
    out = []
    for pub in pd.date_range("2025-12-30", "2026-02-01", freq="1h", tz="UTC"):
        tgt = idx[(idx > pub) & (idx <= pub + timedelta(hours=48))]
        h = (tgt - pub).total_seconds() / 3600
        noise = rng.normal(0, 150 + 90 * h)
        out.append(pd.DataFrame({"startTime": tgt, "publishTime": pub,
                                 "forecast": np.clip(truth[tgt].values + noise + 200, 0, None)}))
    return act, pd.concat(out, ignore_index=True)


@lru_cache(maxsize=1)
def load_actuals():
    if os.environ.get("SAMPLE_DATA") == "1":
        return _sample()[0]
    f = DATA_DIR / "actuals.json"
    if not f.exists():
        download_all()
    df = pd.DataFrame(json.loads(f.read_text()))
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df.rename(columns={"generation": "actual"})[["startTime", "actual"]]
    return df.drop_duplicates("startTime").sort_values("startTime").reset_index(drop=True)


@lru_cache(maxsize=1)
def load_forecasts():
    if os.environ.get("SAMPLE_DATA") == "1":
        return _sample()[1]
    f = DATA_DIR / "forecasts.json"
    if not f.exists():
        download_all()
    df = pd.DataFrame(json.loads(f.read_text()))
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df.rename(columns={"generation": "forecast"})[["startTime", "publishTime", "forecast"]]
    return df.drop_duplicates(["startTime", "publishTime"]).reset_index(drop=True)


if __name__ == "__main__":
    download_all()
    print("Saved to", DATA_DIR)
