from fastapi import FastAPI
from datetime import datetime
from typing import Optional
from wattscheduler.app.core.models import Window
from wattscheduler.app.core.optimizer import find_cheapest_windows
from wattscheduler.app.infra.price_providers import MockPriceProvider, PriceProvider

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def read_root():
    return {"message": "Welcome to Wattscheduler"}


class ScheduleRequest:
    def __init__(self, earliest_start: datetime, latest_end: datetime, duration_minutes: int, num_windows: int = 1):
        self.earliest_start = earliest_start
        self.latest_end = latest_end
        self.duration_minutes = duration_minutes
        self.num_windows = num_windows

from pydantic import BaseModel


class ScheduleRequestDTO(BaseModel):
    earliest_start: str
    latest_end: str
    duration_minutes: int
    num_windows: int = 1


class WindowResponseDTO(BaseModel):
    start_time: str
    end_time: str
    total_price: float
    average_price: float


class ScheduleResponseDTO(BaseModel):
    windows: list[WindowResponseDTO]


def get_price_provider() -> PriceProvider:
    """Get the price provider instance."""
    # For now, use a mock provider. In production, this would be the real provider.
    return MockPriceProvider()


@app.post("/v1/schedule")
async def schedule_task(request: ScheduleRequestDTO) -> ScheduleResponseDTO:
    """
    Schedule a task based on electricity prices.

    Args:
        earliest_start: ISO 8601 formatted datetime string for earliest start time
        latest_end: ISO 8601 formatted datetime string for latest end time
        duration_minutes: Duration of the task in minutes (must be divisible by 15)
        num_windows: Number of optimal windows to return (default: 1)

    Returns:
        List of optimal windows with start/end times and price information
    """
    earliest_start = datetime.fromisoformat(request.earliest_start.replace('Z', '+00:00'))
    latest_end = datetime.fromisoformat(request.latest_end.replace('Z', '+00:00'))

    price_provider = get_price_provider()
    prices = price_provider.get_prices(earliest_start, latest_end)

    if not prices:
        return ScheduleResponseDTO(windows=[])

    from wattscheduler.app.core.models import PricePoint

    price_points = [PricePoint(timestamp=p.timestamp, price=p.price) for p in prices]

    windows = find_cheapest_windows(
        price_points=price_points,
        duration_minutes=request.duration_minutes,
        top_n=request.num_windows
    )

    result = ScheduleResponseDTO(
        windows=[
            WindowResponseDTO(
                start_time=w.start_time.isoformat() + 'Z',
                end_time=w.end_time.isoformat() + 'Z',
                total_price=w.total_price,
                average_price=w.average_price
            )
            for w in windows
        ]
    )

    return result
