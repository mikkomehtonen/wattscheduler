from datetime import datetime, timezone
import json
import urllib.request
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from wattscheduler.app.core.timezone_utils import to_utc_if_naive
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
    entries = [
        {
            "DateTime": "2026-02-14T18:00:00+02:00",
            "PriceWithTax": 0.18569,
        },
        {
            "DateTime": "2026-02-14T18:15:00+02:00",
            "PriceWithTax": 0.19519,
        },
        {
            "DateTime": "2026-02-14T18:30:00+02:00",
            "PriceWithTax": 0.20100,
        },
        {
            "DateTime": "2026-02-14T18:45:00+02:00",
            "PriceWithTax": 0.20100,
        },
    ]
    return json.dumps(entries)


def mock_urlopen(url):
    return MockResponse(_build_mock_price_data())


def test_to_utc_if_naive_winter_helsinki():
    result = to_utc_if_naive(datetime(2026, 2, 14, 0, 0), ZoneInfo("Europe/Helsinki"))
    assert result == datetime(2026, 2, 13, 22, 0, tzinfo=timezone.utc)


def test_to_utc_if_naive_summer_helsinki():
    result = to_utc_if_naive(datetime(2026, 7, 14, 0, 0), ZoneInfo("Europe/Helsinki"))
    assert result == datetime(2026, 7, 13, 21, 0, tzinfo=timezone.utc)


def test_to_utc_if_naive_aware_input_unchanged():
    aware = datetime(2026, 2, 14, 0, 0, tzinfo=ZoneInfo("Europe/Helsinki"))
    result = to_utc_if_naive(aware, ZoneInfo("Europe/Helsinki"))
    assert result == aware
    assert result.tzinfo == aware.tzinfo


def test_to_utc_if_naive_aware_utc_input_unchanged():
    aware = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    result = to_utc_if_naive(aware, ZoneInfo("Europe/Helsinki"))
    assert result == aware


def test_to_utc_if_naive_no_zone_legacy():
    naive = datetime(2026, 2, 14, 0, 0)
    result = to_utc_if_naive(naive, None)
    assert result == naive


@pytest.mark.parametrize(
    "bad_timezone,expected_detail",
    [
        ("Not/A/Zone", "Not/A/Zone"),
        ("EET", "Unknown timezone: EET"),
        ("+02:00", "Unknown timezone: +02:00"),
        ("", "Unknown timezone: "),
    ],
)
def test_invalid_timezone_returns_400(monkeypatch, bad_timezone, expected_detail):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    resp = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T18:00:00",
            "end": "2026-02-14T19:00:00",
            "timezone": bad_timezone,
        },
    )
    assert resp.status_code == 400
    assert expected_detail in resp.json()["detail"]


def test_naive_with_helsinki_returns_utc_window(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    resp = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T18:00:00",
            "end": "2026-02-14T19:00:00",
            "timezone": "Europe/Helsinki",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert parse_iso(data[0]["timestamp"]) == datetime(2026, 2, 14, 16, 0, tzinfo=timezone.utc)
    assert parse_iso(data[-1]["timestamp"]) == datetime(2026, 2, 14, 16, 45, tzinfo=timezone.utc)
    timestamps = [parse_iso(item["timestamp"]) for item in data]
    assert timestamps == sorted(timestamps)


def test_naive_without_timezone_legacy_returns_empty(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    resp = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T18:00:00",
            "end": "2026-02-14T19:00:00",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_aware_input_ignores_timezone_param(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    resp_with_tz = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T18:00:00+02:00",
            "end": "2026-02-14T19:00:00+02:00",
            "timezone": "Europe/Helsinki",
        },
    )
    resp_without_tz = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T18:00:00+02:00",
            "end": "2026-02-14T19:00:00+02:00",
        },
    )
    assert resp_with_tz.status_code == 200
    assert resp_with_tz.json() == resp_without_tz.json()


def test_aware_utc_input_ignores_timezone_param(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    resp = client.get(
        "/v1/prices",
        params={
            "start": "2026-02-14T16:00:00Z",
            "end": "2026-02-14T17:00:00Z",
            "timezone": "Europe/Helsinki",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert parse_iso(data[0]["timestamp"]) == datetime(2026, 2, 14, 16, 0, tzinfo=timezone.utc)
    assert parse_iso(data[-1]["timestamp"]) == datetime(2026, 2, 14, 16, 45, tzinfo=timezone.utc)
