import json
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest

from sqlalchemy import text
from sqlalchemy.orm import Session

from wattscheduler.app.infra.price_providers import CachedPriceProvider
from wattscheduler.app.infra.repositories import SQLAlchemyPriceRepository
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider

HKI = ZoneInfo("Europe/Helsinki")


def helsinki_date_entries(y, m, d, base=0.04):
    anchor = datetime(y, m, d, 0, 0, tzinfo=HKI).astimezone(timezone.utc)
    entries, cur, end = [], anchor - timedelta(hours=4), anchor + timedelta(hours=28)
    while cur < end:
        local = cur.astimezone(HKI)
        if (local.year, local.month, local.day) == (y, m, d):
            entries.append(
                {
                    "DateTime": local.isoformat(),
                    "PriceWithTax": round(base + len(entries) * 0.0001, 5),
                }
            )
        cur += timedelta(minutes=15)
    return entries


def utc_span_for_helsinki_date(y, m, d):
    anchor = datetime(y, m, d, 0, 0, tzinfo=HKI).astimezone(timezone.utc)
    utcs, cur, end = [], anchor - timedelta(hours=4), anchor + timedelta(hours=28)
    while cur < end:
        local = cur.astimezone(HKI)
        if (local.year, local.month, local.day) == (y, m, d):
            utcs.append(cur)
        cur += timedelta(minutes=15)
    return utcs[0], utcs[-1]


class MockResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data.encode("utf-8")

    def close(self):
        pass


def _make_provider(db_session: Session):
    repo = SQLAlchemyPriceRepository(db_session)
    inner = SpotHintaPriceProvider()
    return CachedPriceProvider(inner, repo, "default")


def _row_group(db_session: Session, date: str):
    row = (
        db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt, MIN(timestamp) AS mn, MAX(timestamp) AS mx "
                "FROM price_points WHERE area = 'default' AND date = :date"
            ),
            {"date": date},
        )
        .mappings()
        .one()
    )
    return {
        "cnt": row["cnt"],
        "mn": datetime.fromisoformat(str(row["mn"])),
        "mx": datetime.fromisoformat(str(row["mx"])),
    }


def test_gap_fills_when_next_helsinki_day_published(db_session: Session, monkeypatch):
    first_day = helsinki_date_entries(2026, 6, 30)
    second_day = helsinki_date_entries(2026, 7, 1)

    def mock_urlopen_first(url):
        return MockResponse(json.dumps(first_day + second_day))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_first)

    provider = _make_provider(db_session)
    start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 1, 23, 59, 59, tzinfo=timezone.utc)
    prices = provider.get_prices(start, end)

    assert len(prices) == 84
    assert prices[-1].timestamp == datetime(2026, 7, 1, 20, 45, tzinfo=timezone.utc)
    assert sum(1 for p in prices if p.timestamp.hour >= 21) == 0

    third_day = helsinki_date_entries(2026, 7, 2)

    def mock_urlopen_second(url):
        return MockResponse(json.dumps(second_day + third_day))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_second)

    prices = provider.get_prices(start, end)

    assert len(prices) == 96
    assert prices[0].timestamp == datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
    assert prices[-1].timestamp == datetime(2026, 7, 1, 23, 45, tzinfo=timezone.utc)
    assert sum(1 for p in prices if p.timestamp.hour >= 21) == 12
    assert prices == sorted(prices, key=lambda p: p.timestamp)

    group_0701 = _row_group(db_session, "2026-07-01")
    assert group_0701["cnt"] == 96
    assert group_0701["mn"] == datetime(2026, 6, 30, 21, 0)
    assert group_0701["mx"] == datetime(2026, 7, 1, 20, 45)

    group_0702 = _row_group(db_session, "2026-07-02")
    assert group_0702["cnt"] == 96
    assert group_0702["mn"] == datetime(2026, 7, 1, 21, 0)
    assert group_0702["mx"] == datetime(2026, 7, 2, 20, 45)


def test_spring_forward_dst_day(db_session: Session, monkeypatch):
    entries = helsinki_date_entries(2026, 3, 29)

    def mock_urlopen(url):
        return MockResponse(json.dumps(entries))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 3, 29)
    prices = provider.get_prices(start, end)

    assert len(prices) == 92
    group = _row_group(db_session, "2026-03-29")
    assert group["cnt"] == 92


def test_fall_back_dst_day(db_session: Session, monkeypatch):
    entries = helsinki_date_entries(2026, 10, 25)

    def mock_urlopen(url):
        return MockResponse(json.dumps(entries))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 10, 25)
    prices = provider.get_prices(start, end)

    assert len(prices) == 100
    group = _row_group(db_session, "2026-10-25")
    assert group["cnt"] == 100

    timestamps = [p.timestamp for p in prices]
    assert datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc) in timestamps
    assert datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc) in timestamps


def test_partial_bucket_is_refreshed(db_session: Session, monkeypatch):
    """A day cached while the API was still publishing must be refetched."""
    partial = helsinki_date_entries(2026, 7, 1)[:4]

    def mock_partial(url):
        return MockResponse(json.dumps(partial))

    monkeypatch.setattr(urllib.request, "urlopen", mock_partial)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)
    prices = provider.get_prices(start, end)

    assert len(prices) == 4
    assert _row_group(db_session, "2026-07-01")["cnt"] == 4

    full = helsinki_date_entries(2026, 7, 1)

    def mock_full(url):
        return MockResponse(json.dumps(full))

    monkeypatch.setattr(urllib.request, "urlopen", mock_full)
    prices = provider.get_prices(start, end)

    assert len(prices) == 96
    assert prices[0].timestamp == datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc)
    assert prices[-1].timestamp == datetime(2026, 7, 1, 20, 45, tzinfo=timezone.utc)
    assert _row_group(db_session, "2026-07-01")["cnt"] == 96


def test_refetch_never_shrinks_bucket(db_session: Session, monkeypatch):
    """A refetch returning fewer points must not drop already-cached slots."""
    fifty = helsinki_date_entries(2026, 7, 1)[:50]

    def mock_fifty(url):
        return MockResponse(json.dumps(fifty))

    monkeypatch.setattr(urllib.request, "urlopen", mock_fifty)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)
    assert len(provider.get_prices(start, end)) == 50
    assert _row_group(db_session, "2026-07-01")["cnt"] == 50

    forty = helsinki_date_entries(2026, 7, 1)[:40]

    def mock_forty(url):
        return MockResponse(json.dumps(forty))

    monkeypatch.setattr(urllib.request, "urlopen", mock_forty)
    prices = provider.get_prices(start, end)

    assert len(prices) == 50
    assert _row_group(db_session, "2026-07-01")["cnt"] == 50


def test_refetch_merges_disjoint_slots(db_session: Session, monkeypatch):
    """A refetch with slots the cache lacks is merged, not overwritten."""
    first = helsinki_date_entries(2026, 7, 1)[:4]

    def mock_first(url):
        return MockResponse(json.dumps(first))

    monkeypatch.setattr(urllib.request, "urlopen", mock_first)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)
    assert len(provider.get_prices(start, end)) == 4

    later = helsinki_date_entries(2026, 7, 1)[4:54]

    def mock_later(url):
        return MockResponse(json.dumps(later))

    monkeypatch.setattr(urllib.request, "urlopen", mock_later)
    prices = provider.get_prices(start, end)

    assert len(prices) == 54
    assert _row_group(db_session, "2026-07-01")["cnt"] == 54


def test_partial_bucket_survives_api_failure(db_session: Session, monkeypatch):
    """An upstream outage must not turn a servable partial cache into an error."""
    partial = helsinki_date_entries(2026, 7, 1)[:4]

    def mock_partial(url):
        return MockResponse(json.dumps(partial))

    monkeypatch.setattr(urllib.request, "urlopen", mock_partial)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)
    assert len(provider.get_prices(start, end)) == 4

    def mock_fail(url):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", mock_fail)
    prices = provider.get_prices(start, end)

    assert len(prices) == 4
    assert _row_group(db_session, "2026-07-01")["cnt"] == 4


def test_empty_bucket_propagates_api_failure(db_session: Session, monkeypatch):
    """With nothing cached, an upstream outage still surfaces as an error."""

    def mock_fail(url):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", mock_fail)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)

    with pytest.raises(Exception):
        provider.get_prices(start, end)


def test_complete_bucket_is_not_refetched(db_session: Session, monkeypatch):
    """A complete local-day bucket is served from cache without another API call."""
    entries = helsinki_date_entries(2026, 7, 1)
    calls = {"count": 0}

    def mock_urlopen(url):
        calls["count"] += 1
        return MockResponse(json.dumps(entries))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    provider = _make_provider(db_session)
    start, end = utc_span_for_helsinki_date(2026, 7, 1)

    assert len(provider.get_prices(start, end)) == 96
    assert calls["count"] == 1

    assert len(provider.get_prices(start, end)) == 96
    assert calls["count"] == 1
