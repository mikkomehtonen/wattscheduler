from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
from wattscheduler.app.core.models import PricePoint, Window
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
    start: datetime
    end: datetime
    avg_price_eur_per_kwh: float
    total_price: float
    estimated_cost_eur: float
    start_now_cost_eur: float
    savings_vs_now_eur: float


class ScheduleResponseDTO(BaseModel):
    best_window: WindowResponseDTO
    worst_window: WindowResponseDTO
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
        raise ValueError("dt must be timezone-aware")
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


def find_most_expensive_windows(
    price_points: List[PricePoint], duration_minutes: int, top_n: int = 1
) -> List[Window]:
    """
    Find the most expensive contiguous windows from 15-minute price points.

    Args:
        price_points: List of (timestamp, price) tuples sorted by timestamp
        duration_minutes: Duration of the window in minutes (divisible by 15)
        top_n: Number of top windows to return (default: 1)

    Returns:
        List of Window objects with start_time, end_time, total_price, and average_price
    """
    if not price_points or duration_minutes <= 0:
        return []

    # Validate that duration is divisible by 15
    if duration_minutes % 15 != 0:
        raise ValueError("Duration must be divisible by 15")

    # Calculate number of 15-minute intervals
    intervals = duration_minutes // 15

    # If we need more intervals than we have data, return empty list
    if intervals > len(price_points):
        return []

    windows = []

    # Slide through the price points to find all possible windows
    for i in range(len(price_points) - intervals + 1):
        window_points = price_points[i : i + intervals]

        # Calculate total and average prices for this window
        total_price = sum(point.price for point in window_points)
        average_price = total_price / intervals

        # Create window with start and end times
        start_time = window_points[0].timestamp
        end_time = window_points[-1].timestamp

        window = Window(start_time, end_time, total_price, average_price)
        windows.append(window)

    # Sort windows by total price (descending) and then by start time (ascending) for tie-breaking
    windows.sort(key=lambda w: (-w.total_price, w.start_time))

    # Return top N windows
    return windows[:top_n]


def calculate_window_costs(
    window_dto: WindowResponseDTO,
    price_points: List[PricePoint],
    request: ScheduleRequestDTO,
    earliest_start: datetime,
) -> WindowResponseDTO:
    """Calculate start_now_cost_eur and savings_vs_now_eur for a window."""
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
    window_dto.start_now_cost_eur = start_now_cost_eur
    window_dto.savings_vs_now_eur = start_now_cost_eur - window_dto.estimated_cost_eur

    return window_dto


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
        Best and worst windows with start/end times and price information
    """
    # Use request datetime objects directly
    earliest_start = request.earliest_start
    latest_end = request.latest_end

    price_provider = get_price_provider()
    prices = price_provider.get_prices(earliest_start, latest_end)

    if not prices:
        # Return empty windows for both best and worst
        return ScheduleResponseDTO(
            best_window=WindowResponseDTO(
                start=earliest_start,
                end=earliest_start,
                avg_price_eur_per_kwh=0.0,
                total_price=0.0,
                estimated_cost_eur=0.0,
                start_now_cost_eur=0.0,
                savings_vs_now_eur=0.0,
            ),
            worst_window=WindowResponseDTO(
                start=earliest_start,
                end=earliest_start,
                avg_price_eur_per_kwh=0.0,
                total_price=0.0,
                estimated_cost_eur=0.0,
                start_now_cost_eur=0.0,
                savings_vs_now_eur=0.0,
            ),
            interval_minutes=15,
            currency="EUR",
        )

    price_points = [PricePoint(timestamp=p.timestamp, price=p.price) for p in prices]

    # Find cheapest windows
    cheapest_windows = find_cheapest_windows(
        price_points=price_points, duration_minutes=request.duration_minutes, top_n=1
    )

    # Find most expensive window
    most_expensive_windows = find_most_expensive_windows(
        price_points=price_points, duration_minutes=request.duration_minutes, top_n=1
    )

    # Calculate cost for best window
    best_window = cheapest_windows[0] if cheapest_windows else None
    if best_window:
        best_window_dto = WindowResponseDTO(
            start=best_window.start_time,
            end=best_window.start_time + timedelta(minutes=request.duration_minutes),
            avg_price_eur_per_kwh=best_window.average_price,
            total_price=best_window.total_price,
            estimated_cost_eur=window_cost_eur(best_window.total_price, request.power_kw, 15),
            start_now_cost_eur=0.0,
            savings_vs_now_eur=0.0,
        )
    else:
        best_window_dto = WindowResponseDTO(
            start=earliest_start,
            end=earliest_start,
            avg_price_eur_per_kwh=0.0,
            total_price=0.0,
            estimated_cost_eur=0.0,
            start_now_cost_eur=0.0,
            savings_vs_now_eur=0.0,
        )

    # Calculate cost for worst window
    worst_window = most_expensive_windows[0] if most_expensive_windows else None
    if worst_window:
        worst_window_dto = WindowResponseDTO(
            start=worst_window.start_time,
            end=worst_window.start_time + timedelta(minutes=request.duration_minutes),
            avg_price_eur_per_kwh=worst_window.average_price,
            total_price=worst_window.total_price,
            estimated_cost_eur=window_cost_eur(worst_window.total_price, request.power_kw, 15),
            start_now_cost_eur=0.0,
            savings_vs_now_eur=0.0,
        )
    else:
        worst_window_dto = WindowResponseDTO(
            start=earliest_start,
            end=earliest_start,
            avg_price_eur_per_kwh=0.0,
            total_price=0.0,
            estimated_cost_eur=0.0,
            start_now_cost_eur=0.0,
            savings_vs_now_eur=0.0,
        )

    # Calculate start_now_cost_eur and savings_vs_now_eur for both results
    # Best window calculation
    if best_window:
        best_window_dto = calculate_window_costs(
            best_window_dto, price_points, request, earliest_start
        )

    # Worst window calculation
    if worst_window:
        worst_window_dto = calculate_window_costs(
            worst_window_dto, price_points, request, earliest_start
        )

    result = ScheduleResponseDTO(
        best_window=best_window_dto,
        worst_window=worst_window_dto,
        interval_minutes=15,
        currency="EUR",
    )

    return result
