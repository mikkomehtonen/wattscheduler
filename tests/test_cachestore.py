import pytest
from datetime import datetime, timezone
from wattscheduler.app.infra.cache import CacheStore
from wattscheduler.app.core.models import PricePoint


def test_cache_store():
    """Test the CacheStore functionality."""
    cache_store = CacheStore("test_cache")

    # Test saving and loading prices
    test_prices = [
        PricePoint(datetime(2023, 1, 1, 0, 0), 10.0),
        PricePoint(datetime(2023, 1, 1, 0, 15), 12.0),
    ]

    # Save prices
    cache_store.save_prices("test_area", "2023-01-01", test_prices)

    # Load prices
    loaded_prices = cache_store.load_prices("test_area", "2023-01-01")

    assert len(loaded_prices) == 2
    assert loaded_prices[0].price == 10.0
    assert loaded_prices[1].price == 12.0
