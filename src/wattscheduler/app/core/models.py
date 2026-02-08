from typing import NamedTuple
from datetime import datetime

class PricePoint(NamedTuple):
    timestamp: datetime
    price: float

class Window(NamedTuple):
    start_time: datetime
    end_time: datetime
    total_price: float
    average_price: float
