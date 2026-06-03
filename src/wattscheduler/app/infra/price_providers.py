from typing import List
from datetime import datetime, timezone, timedelta
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
        self, inner_provider: PriceProvider, repository: PriceRepository, area: str = "default"
    ):
        self.inner_provider = inner_provider
        self.repository = repository
        self.area = area

    def _date_str(self, dt: datetime) -> str:
        return dt.date().isoformat()

    def _get_prices_for_date(self, date: datetime) -> List[PricePoint]:
        date_str = self._date_str(date)
        prices = self.repository.load_prices(self.area, date_str)

        if not prices:
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            prices = self.inner_provider.get_prices(start_of_day, end_of_day)
            self.repository.save_prices(self.area, date_str, prices)

        return prices

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        start_date = earliest_start.date()
        end_date = latest_end.date()

        all_prices = []

        current_date = start_date
        while current_date <= end_date:
            start_of_day = datetime.combine(current_date, datetime.min.time())
            if hasattr(earliest_start, "tzinfo") and earliest_start.tzinfo is not None:
                start_of_day = start_of_day.replace(tzinfo=earliest_start.tzinfo)
            prices = self._get_prices_for_date(start_of_day)
            filtered_prices = []
            for p in prices:
                point_timestamp = p.timestamp
                try:
                    if (earliest_start.tzinfo is None) == (point_timestamp.tzinfo is None):
                        if earliest_start <= point_timestamp <= latest_end:
                            filtered_prices.append(p)
                    else:
                        if point_timestamp.tzinfo is not None:
                            point_naive = point_timestamp.replace(tzinfo=None)
                            if earliest_start <= point_naive <= latest_end:
                                filtered_prices.append(p)
                        else:
                            point_aware = point_timestamp.replace(tzinfo=earliest_start.tzinfo)
                            if earliest_start <= point_aware <= latest_end:
                                filtered_prices.append(p)
                except TypeError:
                    if earliest_start <= point_timestamp <= latest_end:
                        filtered_prices.append(p)
            all_prices.extend(filtered_prices)
            current_date += timedelta(days=1)

        all_prices.sort(key=lambda p: p.timestamp)

        return all_prices
