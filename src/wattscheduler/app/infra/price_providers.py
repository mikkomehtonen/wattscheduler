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

    def _get_prices_for_local_date(self, local_date: date) -> List[PricePoint]:
        date_str = local_date.isoformat()
        prices = self.repository.load_prices(self.area, date_str)
        if not prices:
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
            prices = self.inner_provider.get_prices(start_local, end_local)
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
