import os
os.environ["SAMPLE_DATA"] = "1"
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app import analysis

client = TestClient(app)


def test_no_lookahead():
    """The forecast used must have been published before the decision time."""
    r = client.get("/api/day", params={"date": "2026-01-15", "decision_hour": 9}).json()
    assert r["forecast_published_max"] <= r["decision_time"]
    assert len(r["points"]) == 48


def test_metrics():
    m = analysis.metrics(pd.DataFrame({"actual": [10.0, 20.0], "forecast": [12.0, 16.0]}))
    assert m["mae"] == 3 and m["bias"] == -1


def test_endpoints():
    assert client.get("/api/summary").json()["overall"]["n"] > 1000
    assert len(client.get("/api/horizon").json()) > 10
    assert client.get("/api/day", params={"date": "2026-03-01"}).status_code == 404
