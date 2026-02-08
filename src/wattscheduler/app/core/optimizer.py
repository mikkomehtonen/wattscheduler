from typing import List
from .models import PricePoint, Window

def find_cheapest_windows(price_points: List[PricePoint], duration_minutes: int, top_n: int = 1) -> List[Window]:
    """
    Find the cheapest contiguous windows from 15-minute price points.

    Args:
        price_points: List of (timestamp, price) tuples sorted by timestamp
        duration_minutes: Duration of the window in minutes (divisible by 15)
        top_n: Number of top windows to return

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
        window_points = price_points[i:i + intervals]

        # Calculate total and average prices for this window
        total_price = sum(point.price for point in window_points)
        average_price = total_price / intervals

        # Create window with start and end times
        start_time = window_points[0].timestamp
        end_time = window_points[-1].timestamp

        window = Window(start_time, end_time, total_price, average_price)
        windows.append(window)

    # Sort windows by total price (ascending) and then by start time (ascending) for tie-breaking
    windows.sort(key=lambda w: (w.total_price, w.start_time))

    # Return top N windows
    return windows[:top_n]
