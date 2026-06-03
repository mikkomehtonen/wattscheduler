import pytest
from datetime import datetime, timezone
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.core.optimizer import find_cheapest_windows
from wattscheduler.app.infra.price_providers import CachedPriceProvider, MockPriceProvider
from wattscheduler.app.infra.repositories import SQLAlchemyPriceRepository
from sqlalchemy.orm import Session


def test_find_cheapest_windows():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
        PricePoint(datetime(2023, 1, 1, 0, 30), 8.0),
        PricePoint(datetime(2023, 1, 1, 0, 45), 15.0),
        PricePoint(datetime(2023, 1, 1, 1, 0), 9.0),
        PricePoint(datetime(2023, 1, 1, 1, 15), 11.0),
    ]

    result = find_cheapest_windows(price_points, 60, 1)

    assert len(result) == 1
    window = result[0]
    assert window.total_price == 43.0
    assert window.average_price == 10.75
    assert window.start_time == datetime(2023, 1, 1, 0, 30)
    assert window.end_time == datetime(2023, 1, 1, 1, 15)


def test_find_top_n_windows():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
        PricePoint(datetime(2023, 1, 1, 0, 30), 8.0),
        PricePoint(datetime(2023, 1, 1, 0, 45), 15.0),
        PricePoint(datetime(2023, 1, 1, 1, 0), 9.0),
        PricePoint(datetime(2023, 1, 1, 1, 15), 11.0),
    ]

    result = find_cheapest_windows(price_points, 30, 2)

    assert len(result) == 2
    assert result[0].total_price == 20.0
    assert result[0].average_price == 10.0
    assert result[0].start_time == datetime(2023, 1, 1, 0, 15)
    assert result[1].total_price == 20.0
    assert result[1].average_price == 10.0
    assert result[1].start_time == datetime(2023, 1, 1, 1, 0)


def test_tie_breaking():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 30), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 45), 10.0),
    ]

    result = find_cheapest_windows(price_points, 30, 2)

    assert len(result) == 2
    assert result[0].start_time == datetime(2023, 1, 1, 0, 0)
    assert result[1].start_time == datetime(2023, 1, 1, 0, 15)


def test_empty_input():
    result = find_cheapest_windows([], 60, 1)
    assert len(result) == 0


def test_invalid_duration():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
    ]

    with pytest.raises(ValueError):
        find_cheapest_windows(price_points, 25, 1)


def test_duration_larger_than_data():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
    ]

    result = find_cheapest_windows(price_points, 120, 1)
    assert len(result) == 0


def test_cached_price_provider_simple(db_session: Session):
    mock_inner = MockPriceProvider()
    repo = SQLAlchemyPriceRepository(db_session)
    cached_provider = CachedPriceProvider(mock_inner, repo, "test_area")

    start = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 1, 0, tzinfo=timezone.utc)
    prices = cached_provider.get_prices(start, end)

    assert len(prices) == 5
    assert prices[0].price == 10.0
    assert prices[1].price == 12.0
