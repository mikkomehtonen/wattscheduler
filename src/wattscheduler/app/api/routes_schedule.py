from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
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


def ceil_to_interval(dt, minutes):
    """Round datetime up to the next interval boundary."""
    # Convert to UTC for consistent calculations
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Get seconds since epoch
    seconds_since_epoch = int(dt.timestamp())
    # Round up to the next interval
    interval_seconds = minutes * 60
    rounded_up_seconds = (
        (seconds_since_epoch + interval_seconds - 1) // interval_seconds
    ) * interval_seconds
    return datetime.fromtimestamp(rounded_up_seconds, tz=timezone.utc)


def window_cost_eur(total_price, power_kw, interval_minutes):
    """Calculate cost in EUR for a window.

    Args:
        total_price: Sum of prices over the window (EUR/kWh)
        power_kw: Power consumption in kW
        interval_minutes: Duration of each slot in minutes (15)

    Returns:
        Cost in EUR
    """
    return total_price * power_kw * (interval_minutes / 60.0)


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

    # Calculate cost for each window
    result = ScheduleResponseDTO(
        results=[
            WindowResponseDTO(
                start=w.start_time.isoformat(),
                end=(w.start_time + timedelta(minutes=request.duration_minutes)).isoformat(),
                average_price=w.average_price,
                total_price=w.total_price,
                estimated_cost_eur=window_cost_eur(w.total_price, request.power_kw, 15),
                start_now_cost_eur=0.0,
                savings_vs_now_eur=0.0,
            )
            for w in windows
        ],
        interval_minutes=15,
        currency="EUR",
    )

    # Calculate start_now_cost_eur and savings_vs_now_eur for each result
    for i, window in enumerate(result.results):
        # 1) Get current time in UTC
        now = datetime.now(timezone.utc)

        # 2) Round up to next 15-minute slot
        now_rounded = ceil_to_interval(now, 15)

        # 3) Start now is max of rounded time and earliest start
        start_now = max(now_rounded, earliest_start)

        # 4) End now is start now plus duration
        end_now = start_now + timedelta(minutes=request.duration_minutes)

        # 5) Build list of price points in [start_now, end_now)
        start_now_total_price = 0.0
        for price_point in price_points:
            if start_now <= price_point.timestamp < end_now:
                start_now_total_price += price_point.price

        # 6) Calculate start now cost using our helper
        start_now_cost_eur = window_cost_eur(start_now_total_price, request.power_kw, 15)

        # 7) Calculate savings
        result.results[i].start_now_cost_eur = start_now_cost_eur
        result.results[i].savings_vs_now_eur = (
            start_now_cost_eur - result.results[i].estimated_cost_eur
        )

    return result
