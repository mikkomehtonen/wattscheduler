from fastapi import APIRouter
from datetime import datetime, timedelta
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.core.optimizer import find_cheapest_windows
from wattscheduler.app.infra.cache import CacheStore
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.infra.price_providers import CachedPriceProvider
from pydantic import BaseModel, Field
from typing import List

router = APIRouter()


class ScheduleRequestDTO(BaseModel):
    earliest_start: datetime
    latest_end: datetime
    duration_minutes: int
    power_kw: float = Field(gt=0)
    top_n: int = 1


class WindowResponseDTO(BaseModel):
    start: str
    end: str
    average_price: float
    total_price: float
    estimated_cost_eur: float
    start_now_cost_eur: float
    savings_vs_now_eur: float


class ScheduleResponseDTO(BaseModel):
    results: List[WindowResponseDTO]
    interval_minutes: int
    currency: str


def get_price_provider():
    """Get the price provider - can be either mock or real data"""
    # Use real data provider with caching
    cache_store = CacheStore("default_cache")
    real_provider = SpotHintaPriceProvider()
    # Create cached provider, but handle the type mismatch gracefully
    return CachedPriceProvider(real_provider, cache_store, "default")


@router.post("/v1/schedule")
async def schedule_task(request: ScheduleRequestDTO) -> ScheduleResponseDTO:
    """
    Schedule a task based on electricity prices.

    Args:
        earliest_start: Datetime for earliest start time
        latest_end: Datetime for latest end time
        duration_minutes: Duration of the task in minutes (must be divisible by 15)
        power_kw: Power consumption of the appliance in kilowatts
        top_n: Number of optimal windows to return (default: 1)

    Returns:
        List of optimal windows with start/end times and price information
    """
    # Use request datetime objects directly
    earliest_start = request.earliest_start
    latest_end = request.latest_end

    price_provider = get_price_provider()
    prices = price_provider.get_prices(earliest_start, latest_end)

    if not prices:
        return ScheduleResponseDTO(results=[], interval_minutes=15, currency="EUR")

    price_points = [PricePoint(timestamp=p.timestamp, price=p.price) for p in prices]

    windows = find_cheapest_windows(
        price_points=price_points, duration_minutes=request.duration_minutes, top_n=request.top_n
    )

    # Compute cost based on power consumption (kW * hours * price)
    # Duration in minutes, convert to hours (0.25 = 15 minutes in hours)
    duration_hours = request.duration_minutes / 60.0

    def calculate_cost(price_per_kwh: float) -> float:
        # Cost = price_per_kwh * power_kw * duration_hours
        # Spot-Hinta PriceWithTax is already EUR/kWh, no /1000 conversion needed
        return price_per_kwh * request.power_kw * duration_hours

    # Calculate cost if started now (rounded to next 15-minute slot)
    now = datetime.now(earliest_start.tzinfo)
    # Round up to next 15-minute interval
    minutes_to_add = (15 - (now.minute % 15)) % 15
    if minutes_to_add == 0:
        minutes_to_add = 15
    start_now = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)

    # Find the current price at this time
    current_price = 0
    for p in prices:
        if start_now <= p.timestamp:
            current_price = p.price
            break
    start_now_cost = calculate_cost(current_price)

    # Create response with all required fields
    result = ScheduleResponseDTO(
        results=[
            WindowResponseDTO(
                start=w.start_time.isoformat(),
                end=(w.start_time + timedelta(minutes=request.duration_minutes)).isoformat(),
                average_price=w.average_price,
                total_price=w.total_price,
                estimated_cost_eur=calculate_cost(w.total_price),
                start_now_cost_eur=start_now_cost,
                savings_vs_now_eur=start_now_cost - calculate_cost(w.total_price),
            )
            for w in windows
        ],
        interval_minutes=15,
        currency="EUR",
    )

    return result
