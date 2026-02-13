from typing import List
from datetime import datetime
from wattscheduler.app.core.models import PricePoint
import json
from pathlib import Path


class CacheStore:
    """Handles caching of price data to files."""

    def __init__(self, cache_dir: str = "data/cache/prices"):
        """
        Initialize the cache store.

        Args:
            cache_dir: Directory where cache files are stored
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, area: str, date_str: str) -> Path:
        """
        Get the path to a cache file for a given area and date.

        Args:
            area: The area identifier
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Path to the cache file
        """
        return self.cache_dir / area / f"{date_str}.json"

    def load_prices(self, area: str, date_str: str) -> List[PricePoint]:
        """
        Load price points from cache.

        Args:
            area: The area identifier
            date_str: Date string in YYYY-MM-DD format

        Returns:
            List of PricePoint objects or empty list if cache miss
        """
        cache_path = self._get_cache_path(area, date_str)
        if not cache_path.exists():
            return []

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                return [
                    PricePoint(
                        timestamp=datetime.fromisoformat(entry['timestamp']),
                        price=entry['price']
                    )
                    for entry in data
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            # If cache file is corrupted, return empty list
            return []

    def save_prices(self, area: str, date_str: str, prices: List[PricePoint]) -> None:
        """
        Save price points to cache.

        Args:
            area: The area identifier
            date_str: Date string in YYYY-MM-DD format
            prices: List of PricePoint objects to cache
        """
        cache_path = self._get_cache_path(area, date_str)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = [
                {
                    'timestamp': price.timestamp.isoformat(),
                    'price': price.price
                }
                for price in prices
            ]
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception:
            # Silently fail to avoid breaking the application
            pass
