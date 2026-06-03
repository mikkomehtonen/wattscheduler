from typing import List, Protocol
from wattscheduler.app.core.models import PricePoint


class PriceRepository(Protocol):
    def load_prices(self, area: str, date_str: str) -> List[PricePoint]: ...
    def save_prices(self, area: str, date_str: str, prices: List[PricePoint]) -> None: ...
