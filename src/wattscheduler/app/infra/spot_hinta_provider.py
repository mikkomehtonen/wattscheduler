from typing import List
from datetime import datetime, timezone
from wattscheduler.app.core.models import PricePoint
import urllib.request
import json


class SpotHintaPriceProvider:
    """Price provider that fetches real electricity prices from the Finnish Spot-Hinta API."""

    def __init__(self, api_url: str = "https://api.spot-hinta.fi/TodayAndDayForward"):
        """
        Initialize the Spot-Hinta price provider.

        Args:
            api_url: The URL of the Finnish electricity price API
        """
        self.api_url = api_url

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        """
        Get real electricity prices from the Finnish Spot-Hinta API for a given time range.

        Args:
            earliest_start: The earliest start time for the price data
            latest_end: The latest end time for the price data

        Returns:
            List of PricePoint objects within the time range
        """
        # Make request to the Finnish electricity price API using urllib
        try:
            response = urllib.request.urlopen(self.api_url)
            data = response.read().decode('utf-8')
            parsed_data = json.loads(data)
        except Exception as e:
            # If API is not accessible, raise the exception
            raise Exception(f"Failed to fetch prices from API: {str(e)}")

        # The API returns data with timestamps and prices
        # Format: [{"timestamp": "2024-01-01T00:00:00+02:00", "price": 15.2}, ...]
        prices = []

        # Process each price entry from the API
        for item in parsed_data:
            timestamp_str = item.get('DateTime')
            price = item.get('PriceWithTax')

            # Parse the timestamp string to datetime with proper timezone handling
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            # If the timestamp is timezone-aware, convert it to UTC
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(timezone.utc)

            # Only include prices within our requested time range
            if earliest_start <= timestamp <= latest_end:
                prices.append(PricePoint(timestamp, price))

        # Sort prices by timestamp
        prices.sort(key=lambda p: p.timestamp)

        return prices
