import pytest
from datetime import datetime, timezone
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.core.models import PricePoint

# Mock the urllib request to avoid actual API calls
class MockResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data.encode('utf-8')

    def close(self):
        pass

# Mock the urllib.request.urlopen to return our test data
import urllib.request

original_urlopen = urllib.request.urlopen

def mock_urlopen(url):
    # This is test data that matches what the API would return
    # The API returns data in Finnish time (UTC+2), so we need to adjust times accordingly
    test_data = '''[
        {
            "Rank": 20,
            "DateTime": "2026-02-10T00:00:00+02:00",
            "PriceNoTax": 0.12001,
            "PriceWithTax": 0.15061
        },
        {
            "Rank": 10,
            "DateTime": "2026-02-10T00:15:00+02:00",
            "PriceNoTax": 0.11269,
            "PriceWithTax": 0.14143
        }
    ]'''
    return MockResponse(test_data)

def test_spot_hinta_provider():
    """Test that SpotHintaPriceProvider correctly parses mock API data."""
    # Set up the mock
    urllib.request.urlopen = mock_urlopen

    try:
        provider = SpotHintaPriceProvider()
        # The API returns Finnish time (UTC+2), so we need to adjust our test range
        # If API returns times like 2026-02-10T00:00:00+02:00 (which is 2026-02-09T22:00:00+00:00 in UTC)
        # Then for testing purposes, we need to adjust our time window accordingly
        start_time = datetime(2026, 2, 9, 22, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 9, 23, 0, tzinfo=timezone.utc)

        prices = provider.get_prices(start_time, end_time)

        assert len(prices) == 2
        assert prices[0].price == 0.15061
        assert prices[1].price == 0.14143

        # Verify timestamps are properly converted to UTC
        # The API values are in Finnish time (UTC+2), when converted to UTC they become:
        assert prices[0].timestamp == datetime(2026, 2, 9, 22, 0, tzinfo=timezone.utc)
        assert prices[1].timestamp == datetime(2026, 2, 9, 22, 15, tzinfo=timezone.utc)
    finally:
        # Restore original function
        urllib.request.urlopen = original_urlopen

if __name__ == "__main__":
    test_spot_hinta_provider()
    print("All tests passed!")
