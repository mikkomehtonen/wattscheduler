from typing import List, cast
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.infra.db_models import PricePointModel


def _utc(dt: datetime) -> datetime:
    """Attach UTC timezone to a naive datetime.

    Assumes all naive datetimes stored in the database are UTC.
    This invariant is maintained by SpotHintaPriceProvider which normalizes
    to UTC before storing.
    """
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class SQLAlchemyPriceRepository:
    def __init__(self, session: Session):
        self.session = session

    def load_prices(self, area: str, date_str: str) -> List[PricePoint]:
        rows = (
            self.session.query(PricePointModel)
            .filter(PricePointModel.area == area, PricePointModel.date == date_str)
            .order_by(PricePointModel.timestamp.asc())
            .all()
        )
        return [
            PricePoint(timestamp=_utc(cast(datetime, row.timestamp)), price=cast(float, row.price))
            for row in rows
        ]

    def save_prices(self, area: str, date_str: str, prices: List[PricePoint]) -> None:
        # Delete any existing rows for this area/date to avoid unique constraint
        # conflicts when re-caching data.
        self.session.query(PricePointModel).filter(
            PricePointModel.area == area, PricePointModel.date == date_str
        ).delete()
        for pp in prices:
            row = PricePointModel(area=area, date=date_str, timestamp=pp.timestamp, price=pp.price)
            self.session.add(row)
        self.session.commit()
