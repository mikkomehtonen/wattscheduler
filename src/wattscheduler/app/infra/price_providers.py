from typing import List
from datetime import datetime, timezone
from wattscheduler.app.core.models import PricePoint


class PriceProvider:
    """Abstract base class for price providers."""

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        """
        Get electricity prices for a given time range.

        Args:
            earliest_start: The earliest start time for the price data
            latest_end: The latest end time for the price data

        Returns:
            List of PricePoint objects within the time range
        """
        raise NotImplementedError


class MockPriceProvider(PriceProvider):
    """Mock price provider for testing and development."""

    def __init__(self):
        """Initialize mock price provider with hardcoded test data."""
        # For simplicity, we'll use fixed data that matches tests
        # This provides 15-minute intervals from 00:00 to 01:30 UTC
        self._price_data = [
            PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0),
            PricePoint(datetime(2023, 1, 1, 0, 15, tzinfo=timezone.utc), 12.0),
            PricePoint(datetime(2023, 1, 1, 0, 30, tzinfo=timezone.utc), 8.0),
            PricePoint(datetime(2023, 1, 1, 0, 45, tzinfo=timezone.utc), 15.0),
            PricePoint(datetime(2023, 1, 1, 1, 0, tzinfo=timezone.utc), 9.0),
            PricePoint(datetime(2023, 1, 1, 1, 15, tzinfo=timezone.utc), 11.0),
        ]

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        """
        Get mock electricity prices for a given time range.

        Args:
            earliest_start: The earliest start time for the price data
            latest_end: The latest end time for the price data

        Returns:
            List of PricePoint objects within the time range
        """
        result = []
        for price_point in self._price_data:
            # Make sure we're comparing timezone-aware datetimes
            if price_point.timestamp >= earliest_start and price_point.timestamp <= latest_end:
                result.append(price_point)
        return result
