"""All the maths. Times are UTC (= UK time in January, so no DST issues)."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .data import FIRST_DELIVERY, LAST_DELIVERY, load_actuals, load_forecasts


def _num(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def metrics(df: pd.DataFrame) -> dict:
    """Error metrics. Error = forecast - actual (positive = over-forecast)."""
    d = df.dropna(subset=["actual", "forecast"])
    if d.empty:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "mape": None, "p90_abs": None}
    e = d["forecast"] - d["actual"]
    nz = d["actual"] > 0
    return {
        "n": int(len(d)),
        "mae": _num(e.abs().mean()),
        "rmse": _num(np.sqrt((e ** 2).mean())),
        "bias": _num(e.mean()),
        "mape": _num((e[nz].abs() / d.loc[nz, "actual"]).mean() * 100),
        "p90_abs": _num(e.abs().quantile(0.9)),
    }


def decision_frame(decision_hour: int) -> pd.DataFrame:
    """For every half-hour in the delivery window: actual + the LATEST forecast that
    existed at the decision time (decision_hour o'clock on the day before delivery)."""
    act = load_actuals()
    fc = load_forecasts().copy()
    fc["delivery_date"] = fc["startTime"].dt.floor("D")
    cutoff = fc["delivery_date"] - pd.Timedelta(days=1) + pd.Timedelta(hours=decision_hour)
    fc = fc[fc["publishTime"] <= cutoff].sort_values("publishTime")
    fc = fc.drop_duplicates("startTime", keep="last")[["startTime", "publishTime", "forecast"]]
    df = act.merge(fc, on="startTime", how="left")
    df["delivery_date"] = df["startTime"].dt.floor("D").dt.date
    df = df[(df["delivery_date"] >= FIRST_DELIVERY) & (df["delivery_date"] <= LAST_DELIVERY)].copy()
    df["error"] = df["forecast"] - df["actual"]
    return df


def config() -> dict:
    days, d = [], FIRST_DELIVERY
    while d <= LAST_DELIVERY:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return {"delivery_days": days, "default_decision_hour": 9}


def day_view(day: date, decision_hour: int) -> dict:
    full = decision_frame(decision_hour)
    df = full[full["delivery_date"] == day]
    err = full["error"].dropna()
    # Uncertainty band: actual ≈ forecast - error, using the 10th/90th percentile of past errors.
    q10, q90 = (err.quantile(0.1), err.quantile(0.9)) if len(err) else (0, 0)
    points = []
    for r in df.itertuples():
        f = _num(r.forecast)
        points.append({
            "time": r.startTime.isoformat(),
            "actual": _num(r.actual),
            "forecast": f,
            "low": None if f is None else max(0.0, f - q90),
            "high": None if f is None else max(0.0, f - q10),
        })
    pub = df["publishTime"].dropna()
    return {
        "date": day.isoformat(),
        "decision_time": (pd.Timestamp(day, tz="UTC") - pd.Timedelta(days=1)
                          + pd.Timedelta(hours=decision_hour)).isoformat(),
        "forecast_published_min": pub.min().isoformat() if len(pub) else None,
        "forecast_published_max": pub.max().isoformat() if len(pub) else None,
        "forecast_mwh": _num(df["forecast"].sum() / 2),   # MW over 30 min -> MWh
        "actual_mwh": _num(df["actual"].sum() / 2),
        "band_p10_p90": [_num(q10), _num(q90)],
        "metrics": metrics(df),
        "points": points,
    }


def summary(decision_hour: int) -> dict:
    df = decision_frame(decision_hour)
    daily = [{"date": d.isoformat(), **metrics(g)} for d, g in df.groupby("delivery_date")]
    hourly = [{"hour": int(h), **metrics(g)} for h, g in df.groupby(df["startTime"].dt.hour)]
    err = df["error"].dropna()
    pct = {f"p{p}": _num(err.quantile(p / 100)) for p in (5, 10, 25, 50, 75, 90, 95)} if len(err) else {}
    return {"overall": metrics(df), "daily": daily, "by_hour_of_day": hourly, "error_percentiles": pct}


def horizon_view() -> list:
    """MAE as a function of how far ahead the forecast was published (all forecasts, not just the decision one)."""
    fc = load_forecasts().merge(load_actuals(), on="startTime", how="inner")
    fc["delivery_date"] = fc["startTime"].dt.floor("D").dt.date
    fc = fc[(fc["delivery_date"] >= FIRST_DELIVERY) & (fc["delivery_date"] <= LAST_DELIVERY)].copy()
    fc["horizon_h"] = ((fc["startTime"] - fc["publishTime"]).dt.total_seconds() // 3600).astype(int)
    fc = fc[(fc["horizon_h"] >= 0) & (fc["horizon_h"] <= 48)]
    return [{"horizon_h": int(h), **metrics(g)} for h, g in fc.groupby("horizon_h")]
