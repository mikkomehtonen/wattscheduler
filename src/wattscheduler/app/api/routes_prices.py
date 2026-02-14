from fastapi import APIRouter
from datetime import datetime
from wattscheduler.app.infra.price_providers import PriceProvider, CachedPriceProvider
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.infra.cache import CacheStore
from wattscheduler.app.core.models import PricePoint
from pydantic import BaseModel
from typing import List, Any

router = APIRouter()


class PriceResponseDTO(BaseModel):
    timestamp: datetime
    price: float


def get_price_provider():
    """Get the price provider - can be either mock or real data"""
    # Use real data provider with caching
    cache_store = CacheStore("default_cache")
    real_provider = SpotHintaPriceProvider()
    # Create cached provider
    return CachedPriceProvider(real_provider, cache_store, "default")


@router.get("/v1/prices")
async def get_prices(start: datetime, end: datetime) -> List[PriceResponseDTO]:
    """Get price data for a time range at 15-minute resolution."""
    price_provider = get_price_provider()
    prices = price_provider.get_prices(start, end)

    # Convert to the expected format
    result = []
    for p in prices:
        result.append(PriceResponseDTO(timestamp=p.timestamp, price=p.price))

    return result
