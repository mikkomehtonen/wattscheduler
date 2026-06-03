from fastapi import APIRouter, Depends
from datetime import datetime
from wattscheduler.app.infra.price_providers import PriceProvider
from wattscheduler.app.api.deps import get_price_provider
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
    price_provider: PriceProvider = Depends(get_price_provider),
) -> List[PriceResponseDTO]:
    prices = price_provider.get_prices(start, end)

    result = []
    for p in prices:
        result.append(PriceResponseDTO(timestamp=p.timestamp, price=p.price))

    return result
