from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
from wattscheduler.app.core.models import PricePoint, Window
from wattscheduler.app.core.optimizer import find_cheapest_windows
from wattscheduler.app.infra.cache import CacheStore
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.infra.price_providers import CachedPriceProvider
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ScheduleRequestDTO(BaseModel):
    earliest_start: str
    latest_end: str
    duration_minutes: int
    top_n: int = 1


class WindowResponseDTO(BaseModel):
    start: str
    end: str
    average_price: float
    total_price: float


class ScheduleResponseDTO(BaseModel):
    results: List[WindowResponseDTO]
    unit: str
    interval_minutes: int


def get_price_provider():
    """Get the price provider - can be either mock or real data"""
    # Use real data provider with caching
    cache_store = CacheStore("default_cache")
    real_provider = SpotHintaPriceProvider()
    return CachedPriceProvider(real_provider, cache_store, "default")


@router.post("/v1/schedule")
async def schedule_task(request: ScheduleRequestDTO) -> ScheduleResponseDTO:
    """
    Schedule a task based on electricity prices.

    Args:
        earliest_start: ISO 8601 formatted datetime string for earliest start time
        latest_end: ISO 8601 formatted datetime string for latest end time
        duration_minutes: Duration of the task in minutes (must be divisible by 15)
        top_n: Number of optimal windows to return (default: 1)

    Returns:
        List of optimal windows with start/end times and price information
    """
    earliest_start = datetime.fromisoformat(request.earliest_start.replace('Z', '+00:00'))
    latest_end = datetime.fromisoformat(request.latest_end.replace('Z', '+00:00'))

    price_provider = get_price_provider()
    prices = price_provider.get_prices(earliest_start, latest_end)

    if not prices:
        return ScheduleResponseDTO(results=[], unit="EUR/MWh", interval_minutes=15)

    price_points = [PricePoint(timestamp=p.timestamp, price=p.price) for p in prices]

    windows = find_cheapest_windows(
        price_points=price_points,
        duration_minutes=request.duration_minutes,
        top_n=request.top_n
    )

    result = ScheduleResponseDTO(
        results=[
            WindowResponseDTO(
                start=w.start_time.isoformat() + 'Z',
                end=w.end_time.isoformat() + 'Z',
                average_price=w.average_price,
                total_price=w.total_price
            )
            for w in windows
        ],
        unit="EUR/MWh",
        interval_minutes=15
    )

    return result
