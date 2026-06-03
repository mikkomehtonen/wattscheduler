from sqlalchemy.orm import Session
from fastapi import Depends
from wattscheduler.app.infra.db import get_db
from wattscheduler.app.infra.price_providers import CachedPriceProvider
from wattscheduler.app.infra.repositories import SQLAlchemyPriceRepository
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider


def get_price_provider(db: Session = Depends(get_db)) -> CachedPriceProvider:
    repo = SQLAlchemyPriceRepository(db)
    real_provider = SpotHintaPriceProvider()
    return CachedPriceProvider(real_provider, repo, "default")
