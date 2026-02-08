import pytest
from datetime import datetime
from wattscheduler.app.core.models import PricePoint, Window
from wattscheduler.app.core.optimizer import find_cheapest_windows

def test_find_cheapest_windows():
    # Test data with 15-minute intervals
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
        PricePoint(datetime(2023, 1, 1, 0, 30), 8.0),
        PricePoint(datetime(2023, 1, 1, 0, 45), 15.0),
        PricePoint(datetime(2023, 1, 1, 1, 0), 9.0),
        PricePoint(datetime(2023, 1, 1, 1, 15), 11.0),
    ]

    # Test finding cheapest 1-hour (60-minute) window
    result = find_cheapest_windows(price_points, 60, 1)

    # Should return 1 window
    assert len(result) == 1

    # Cheapest 1-hour window should be from 00:30-01:15 with prices 8, 15, 9, 11
    # Total price = 43, average = 10.75
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

    # Test finding top 2 cheapest 30-minute (30-minute) windows
    result = find_cheapest_windows(price_points, 30, 2)

    # Should return 2 windows
    assert len(result) == 2

    # First should be the cheapest (00:15-00:30 with prices 12.0, 8.0) = 20.0 total
    assert result[0].total_price == 20.0
    assert result[0].average_price == 10.0
    assert result[0].start_time == datetime(2023, 1, 1, 0, 15)

    # Second should be the next cheapest (01:00-01:15 with prices 9.0, 11.0) = 20.0 total
    # But since they have same price, tie-break by earliest start
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

    # All windows have same price, so earliest start time should win
    result = find_cheapest_windows(price_points, 30, 2)

    # Should return 2 windows
    assert len(result) == 2

    # First window should be 00:00-00:30 (earlier start time)
    assert result[0].start_time == datetime(2023, 1, 1, 0, 0)

    # Second window should be 00:15-00:45 (later start time)
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
        find_cheapest_windows(price_points, 25, 1)  # Not divisible by 15

def test_duration_larger_than_data():
    price_points = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
    ]

    result = find_cheapest_windows(price_points, 120, 1)  # 2 hours, more than data
    assert len(result) == 0
