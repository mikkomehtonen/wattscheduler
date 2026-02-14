from datetime import datetime, timezone
from fastapi.testclient import TestClient

from wattscheduler.app.main import app

client = TestClient(app)


def parse_iso(dt_str: str) -> datetime:
    # Accept both "...Z" and "...+00:00"
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)

def test_schedule_30min_cost_and_window_regression(monkeypatch):
    """
    Regression test for:
    - best window selection (30 min = 2 slots)
    - estimated_cost_eur calculation using power_kw and 15-min slots
    - deterministic "start_now" by forcing current time
    """

    # Freeze "now" to earliest_start so start_now window becomes deterministic.
    # Adjust the import path below if your schedule route uses a different module.
    import wattscheduler.app.api.routes_schedule as routes_schedule

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 2, 14, 16, 0, tzinfo=timezone.utc)

    # If your code calls datetime.now(...) inside routes_schedule, this makes it deterministic.
    monkeypatch.setattr(routes_schedule, "datetime", FrozenDateTime)

    payload = {
        "duration_minutes": 30,
        "power_kw": 2.0,
        # 18:00+02:00 == 16:00 UTC
        "earliest_start": "2026-02-14T16:00:00+00:00",
        # 23:00+02:00 == 21:00 UTC
        "latest_end": "2026-02-14T21:00:00+00:00",
        "top_n": 1,
    }

    resp = client.post("/v1/schedule", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Depending on your API shape, it might return "results" (list) or direct fields.
    # Your latest response shows "results".
    assert "results" in data and len(data["results"]) == 1
    result = data["results"][0]

    assert parse_iso(result["start"]) == datetime(2026, 2, 14, 20, 30, tzinfo=timezone.utc)
    assert parse_iso(result["end"]) == datetime(2026, 2, 14, 21, 0, tzinfo=timezone.utc)

    # From your provided data:
    # 20:30 = 0.14873, 20:45 = 0.13992
    expected_total_price = 0.14873 + 0.13992  # 0.28865

    # Cost formula for 15-minute slots (EUR/kWh):
    # cost = sum(price_i * power_kw * 0.25)
    expected_cost = expected_total_price * 2.0 * 0.25  # 0.144325

    assert abs(result["total_price"] - expected_total_price) < 1e-9
    assert abs(result["estimated_cost_eur"] - expected_cost) < 1e-9

    # Since we froze now=16:00 UTC, start_now window is 16:00+16:15:
    # 0.18569 + 0.19519 = 0.38088 -> cost = 0.38088 * 2.0 * 0.25 = 0.19044
    expected_now_cost = (0.18569 + 0.19519) * 2.0 * 0.25
    assert abs(result["start_now_cost_eur"] - expected_now_cost) < 1e-9

    expected_savings = expected_now_cost - expected_cost
    assert abs(result["savings_vs_now_eur"] - expected_savings) < 1e-9
