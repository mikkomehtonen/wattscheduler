from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wattscheduler.app.infra.price_providers import PriceProvider
from wattscheduler.app.api.deps import get_price_provider
from wattscheduler.app.core.timezone_utils import to_utc_if_naive
from pydantic import BaseModel
from typing import List

router = APIRouter()


class PriceResponseDTO(BaseModel):
    timestamp: datetime
    price: float


@router.get("/v1/prices")
async def get_prices(
    start: datetime,
    end: datetime,
    timezone: str | None = None,
    price_provider: PriceProvider = Depends(get_price_provider),
) -> List[PriceResponseDTO]:
    tz: ZoneInfo | None = None
    if timezone is not None:
        try:
            tz = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(status_code=400, detail=f"Unknown timezone: {timezone}")

        # Only accept canonical Area/Location IANA names (or UTC) so that
        # abbreviations and bare fixed offsets are rejected. This is
        # required for the DST correctness the API promises Finnish callers.
        if "/" not in timezone and timezone != "UTC":
            raise HTTPException(status_code=400, detail=f"Unknown timezone: {timezone}")

    start = to_utc_if_naive(start, tz)
    end = to_utc_if_naive(end, tz)

    prices = price_provider.get_prices(start, end)

    result = []
    for p in prices:
        result.append(PriceResponseDTO(timestamp=p.timestamp, price=p.price))

    return result
