from datetime import datetime, timezone
import json
import urllib.request

from fastapi.testclient import TestClient

from wattscheduler.app.main import app

client = TestClient(app)


def parse_iso(dt_str: str) -> datetime:
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)


class MockResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data.encode("utf-8")

    def close(self):
        pass


def _build_mock_price_data():
    """Return JSON string matching Spot-Hinta API format for 2026-02-14."""
    # Times in Finnish time (UTC+2 / EET)
    # The test range is 16:00-21:00 UTC = 18:00-23:00 EET
    entries = [
        {
            "Rank": 1,
            "DateTime": "2026-02-14T18:00:00+02:00",
            "PriceNoTax": 0.14775,
            "PriceWithTax": 0.18569,
        },
        {
            "Rank": 2,
            "DateTime": "2026-02-14T18:15:00+02:00",
            "PriceNoTax": 0.15520,
            "PriceWithTax": 0.19519,
        },
        {
            "Rank": 3,
            "DateTime": "2026-02-14T18:30:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 4,
            "DateTime": "2026-02-14T18:45:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 5,
            "DateTime": "2026-02-14T19:00:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 6,
            "DateTime": "2026-02-14T19:15:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 7,
            "DateTime": "2026-02-14T19:30:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 8,
            "DateTime": "2026-02-14T19:45:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 9,
            "DateTime": "2026-02-14T20:00:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 10,
            "DateTime": "2026-02-14T20:15:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 11,
            "DateTime": "2026-02-14T20:30:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 12,
            "DateTime": "2026-02-14T20:45:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 13,
            "DateTime": "2026-02-14T21:00:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 14,
            "DateTime": "2026-02-14T21:15:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 15,
            "DateTime": "2026-02-14T21:30:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 16,
            "DateTime": "2026-02-14T21:45:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 17,
            "DateTime": "2026-02-14T22:00:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 18,
            "DateTime": "2026-02-14T22:15:00+02:00",
            "PriceNoTax": 0.16000,
            "PriceWithTax": 0.20100,
        },
        {
            "Rank": 19,
            "DateTime": "2026-02-14T22:30:00+02:00",
            "PriceNoTax": 0.11760,
            "PriceWithTax": 0.14873,
        },
        {
            "Rank": 20,
            "DateTime": "2026-02-14T22:45:00+02:00",
            "PriceNoTax": 0.11045,
            "PriceWithTax": 0.13992,
        },
        {
            "Rank": 21,
            "DateTime": "2026-02-14T23:00:00+02:00",
            "PriceNoTax": 0.12730,
            "PriceWithTax": 0.16000,
        },
    ]
    return json.dumps(entries)


def mock_urlopen(url):
    return MockResponse(_build_mock_price_data())


def test_schedule_30min_cost_and_window_regression(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    import wattscheduler.app.api.routes_schedule as routes_schedule

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 2, 14, 16, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(routes_schedule, "datetime", FrozenDateTime)

    payload = {
        "duration_minutes": 30,
        "power_kw": 2.0,
        "earliest_start": "2026-02-14T16:00:00+00:00",
        "latest_end": "2026-02-14T21:00:00+00:00",
        "top_n": 1,
    }

    resp = client.post("/v1/schedule", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "best_window" in data
    result = data["best_window"]

    assert parse_iso(result["start"]) == datetime(2026, 2, 14, 20, 30, tzinfo=timezone.utc)
    assert parse_iso(result["end"]) == datetime(2026, 2, 14, 21, 0, tzinfo=timezone.utc)

    expected_total_price = 0.14873 + 0.13992
    expected_cost = expected_total_price * 2.0 * 0.25

    assert abs(result["total_price"] - expected_total_price) < 1e-9
    assert abs(result["estimated_cost_eur"] - expected_cost) < 1e-9

    expected_now_cost = (0.18569 + 0.19519) * 2.0 * 0.25
    assert abs(result["start_now_cost_eur"] - expected_now_cost) < 1e-9

    expected_savings = expected_now_cost - expected_cost
    assert abs(result["savings_vs_now_eur"] - expected_savings) < 1e-9
