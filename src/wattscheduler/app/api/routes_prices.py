from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from wattscheduler.app.infra.price_providers import CachedPriceProvider
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.infra.repositories import SQLAlchemyPriceRepository
from wattscheduler.app.infra.db import get_db
from pydantic import BaseModel
from typing import List

router = APIRouter()


class PriceResponseDTO(BaseModel):
    timestamp: datetime
    price: float


def get_price_provider(db: Session = Depends(get_db)):
    repo = SQLAlchemyPriceRepository(db)
    real_provider = SpotHintaPriceProvider()
    return CachedPriceProvider(real_provider, repo, "default")


@router.get("/v1/prices")
async def get_prices(
    start: datetime, end: datetime, price_provider=Depends(get_price_provider)
) -> List[PriceResponseDTO]:
    prices = price_provider.get_prices(start, end)

    result = []
    for p in prices:
        result.append(PriceResponseDTO(timestamp=p.timestamp, price=p.price))

    return result
