from typing import List
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.core.ports import PriceRepository


class PriceProvider:
    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        raise NotImplementedError


class MockPriceProvider(PriceProvider):
    def __init__(self):
        self._price_data = [
            PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0),
            PricePoint(datetime(2023, 1, 1, 0, 15, tzinfo=timezone.utc), 12.0),
            PricePoint(datetime(2023, 1, 1, 0, 30, tzinfo=timezone.utc), 8.0),
            PricePoint(datetime(2023, 1, 1, 0, 45, tzinfo=timezone.utc), 15.0),
            PricePoint(datetime(2023, 1, 1, 1, 0, tzinfo=timezone.utc), 9.0),
            PricePoint(datetime(2023, 1, 1, 1, 15, tzinfo=timezone.utc), 11.0),
        ]

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        result = []
        for price_point in self._price_data:
            if price_point.timestamp >= earliest_start and price_point.timestamp <= latest_end:
                result.append(price_point)
        return result


class CachedPriceProvider(PriceProvider):
    def __init__(
        self,
        inner_provider: PriceProvider,
        repository: PriceRepository,
        area: str = "default",
        source_tz: ZoneInfo = ZoneInfo("Europe/Helsinki"),
    ):
        self.inner_provider = inner_provider
        self.repository = repository
        self.area = area
        self.source_tz = source_tz

    def _to_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _local_day_bounds(self, local_date: date) -> tuple[datetime, datetime]:
        start_local = datetime(
            local_date.year, local_date.month, local_date.day, 0, 0, tzinfo=self.source_tz
        )
        next_local_date = local_date + timedelta(days=1)
        end_local = datetime(
            next_local_date.year,
            next_local_date.month,
            next_local_date.day,
            0,
            0,
            tzinfo=self.source_tz,
        )
        return start_local, end_local

    def _expected_slot_count(self, start_local: datetime, end_local: datetime) -> int:
        """Number of 15-minute slots in the local day (96, or 92/100 on DST days)."""
        span = end_local.astimezone(timezone.utc) - start_local.astimezone(timezone.utc)
        return int(span.total_seconds() // 900)

    def _get_prices_for_local_date(self, local_date: date) -> List[PricePoint]:
        date_str = local_date.isoformat()
        prices = self.repository.load_prices(self.area, date_str)
        start_local, end_local = self._local_day_bounds(local_date)
        # A non-empty bucket is not necessarily complete: the Spot-Hinta API can
        # return a partially published day (e.g. while day-ahead prices are being
        # rolled over). Only trust a bucket that covers the whole local day;
        # otherwise refetch and merge by timestamp so cached slots are never lost.
        if len(prices) >= self._expected_slot_count(start_local, end_local):
            return prices
        try:
            fetched = self.inner_provider.get_prices(start_local, end_local)
        except Exception:
            # Upstream unavailable: serve the partial cache rather than failing
            # the request. An empty bucket still propagates the error.
            if prices:
                return prices
            raise
        cached = {p.timestamp: p for p in prices}
        merged = dict(cached)
        merged.update({p.timestamp: p for p in fetched})
        if merged != cached:
            prices = sorted(merged.values(), key=lambda p: p.timestamp)
            self.repository.save_prices(self.area, date_str, prices)
        return prices

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        es = self._to_utc(earliest_start)
        le = self._to_utc(latest_end)
        start_local_date = es.astimezone(self.source_tz).date()
        end_local_date = le.astimezone(self.source_tz).date()
        all_prices: List[PricePoint] = []
        current = start_local_date
        while current <= end_local_date:
            all_prices.extend(self._get_prices_for_local_date(current))
            current += timedelta(days=1)
        filtered = [p for p in all_prices if es <= p.timestamp <= le]
        filtered.sort(key=lambda p: p.timestamp)
        return filtered
