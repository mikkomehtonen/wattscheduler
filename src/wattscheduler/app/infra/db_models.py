from sqlalchemy import Column, Integer, String, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class PricePointModel(Base):
    __tablename__ = "price_points"

    id = Column(Integer, primary_key=True)
    area = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("area", "date", "timestamp", name="uq_area_date_timestamp"),)
