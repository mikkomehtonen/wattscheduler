from typing import List
from datetime import datetime, timezone, timedelta
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.infra.cache import CacheStore


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


class CachedPriceProvider(PriceProvider):
    """Price provider that caches data to files."""

    def __init__(self, inner_provider: PriceProvider, cache_store: CacheStore, area: str = "default"):
        """
        Initialize the cached price provider.

        Args:
            inner_provider: The underlying price provider
            cache_store: The cache store to use
            area: The area identifier
        """
        self.inner_provider = inner_provider
        self.cache_store = cache_store
        self.area = area

    def _date_str(self, dt: datetime) -> str:
        """Get date string in YYYY-MM-DD format."""
        return dt.date().isoformat()

    def _get_prices_for_date(self, date: datetime) -> List[PricePoint]:
        """
        Get prices for a specific date, using cache when possible.

        Args:
            date: Date to get prices for

        Returns:
            List of PricePoint objects for the date
        """
        date_str = self._date_str(date)
        prices = self.cache_store.load_prices(self.area, date_str)

        if not prices:
            # Cache miss, fetch from inner provider and save to cache
            # For simplicity, we'll use the entire date range for each day
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            prices = self.inner_provider.get_prices(start_of_day, end_of_day)
            self.cache_store.save_prices(self.area, date_str, prices)

        return prices

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        """
        Get electricity prices for a given time range, using cache when possible.

        Args:
            earliest_start: The earliest start time for the price data
            latest_end: The latest end time for the price data

        Returns:
            List of PricePoint objects within the time range
        """
        # Get all days in the range
        start_date = earliest_start.date()
        end_date = latest_end.date()

        all_prices = []

        # Process each day in the range
        current_date = start_date
        while current_date <= end_date:
            # Ensure timezone info is preserved when creating start_of_day to match mock data
            start_of_day = datetime.combine(current_date, datetime.min.time())
            if hasattr(earliest_start, 'tzinfo') and earliest_start.tzinfo is not None:
                start_of_day = start_of_day.replace(tzinfo=earliest_start.tzinfo)
            prices = self._get_prices_for_date(start_of_day)
            # Filter prices to only those within the requested range using safe comparison
            filtered_prices = []
            for p in prices:
                # Safely compare timestamps handling timezone-aware vs naive cases
                point_timestamp = p.timestamp
                try:
                    # If both are timezone aware or both are naive do direct comparison
                    if (earliest_start.tzinfo is None) == (point_timestamp.tzinfo is None):
                        if earliest_start <= point_timestamp <= latest_end:
                            filtered_prices.append(p)
                    else:
                        # Mix of aware and naive - convert point_timestamp to naive for comparison
                        if point_timestamp.tzinfo is not None:
                            point_naive = point_timestamp.replace(tzinfo=None)
                            if earliest_start <= point_naive <= latest_end:
                                filtered_prices.append(p)
                        else:
                            # point_timestamp is naive, earliest_start is aware
                            # Convert to aware for comparison using the same timezone as earliest_start
                            point_aware = point_timestamp.replace(tzinfo=earliest_start.tzinfo)
                            if earliest_start <= point_aware <= latest_end:
                                filtered_prices.append(p)
                except TypeError:
                    # Fallback in case of other issues
                    if earliest_start <= point_timestamp <= latest_end:
                        filtered_prices.append(p)
            all_prices.extend(filtered_prices)
            current_date += timedelta(days=1)

        # Sort the prices by timestamp
        all_prices.sort(key=lambda p: p.timestamp)

        return all_prices
