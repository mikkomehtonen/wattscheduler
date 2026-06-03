from datetime import datetime, timezone
from sqlalchemy.orm import Session
from wattscheduler.app.infra.repositories import SQLAlchemyPriceRepository
from wattscheduler.app.core.models import PricePoint


class TestSQLAlchemyPriceRepository:
    def test_load_empty_returns_empty_list(self, db_session: Session):
        repo = SQLAlchemyPriceRepository(db_session)
        prices = repo.load_prices("test_area", "2023-01-01")
        assert prices == []

    def test_save_and_load(self, db_session: Session):
        repo = SQLAlchemyPriceRepository(db_session)
        test_prices = [
            PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0),
            PricePoint(datetime(2023, 1, 1, 0, 15, tzinfo=timezone.utc), 12.0),
        ]

        repo.save_prices("test_area", "2023-01-01", test_prices)
        loaded = repo.load_prices("test_area", "2023-01-01")

        assert len(loaded) == 2
        assert loaded[0].price == 10.0
        assert loaded[1].price == 12.0
        assert loaded[0].timestamp == datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert loaded[1].timestamp == datetime(2023, 1, 1, 0, 15, tzinfo=timezone.utc)

    def test_save_multiple_areas(self, db_session: Session):
        repo = SQLAlchemyPriceRepository(db_session)

        repo.save_prices(
            "area_a",
            "2023-01-01",
            [PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0)],
        )
        repo.save_prices(
            "area_b",
            "2023-01-01",
            [PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 20.0)],
        )

        area_a = repo.load_prices("area_a", "2023-01-01")
        area_b = repo.load_prices("area_b", "2023-01-01")

        assert len(area_a) == 1
        assert area_a[0].price == 10.0
        assert len(area_b) == 1
        assert area_b[0].price == 20.0

    def test_save_multiple_dates(self, db_session: Session):
        repo = SQLAlchemyPriceRepository(db_session)

        repo.save_prices(
            "area",
            "2023-01-01",
            [PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0)],
        )
        repo.save_prices(
            "area",
            "2023-01-02",
            [PricePoint(datetime(2023, 1, 2, 0, 0, tzinfo=timezone.utc), 15.0)],
        )

        day1 = repo.load_prices("area", "2023-01-01")
        day2 = repo.load_prices("area", "2023-01-02")

        assert len(day1) == 1
        assert day1[0].price == 10.0
        assert len(day2) == 1
        assert day2[0].price == 15.0

    def test_save_replaces_existing(self, db_session: Session):
        repo = SQLAlchemyPriceRepository(db_session)
        repo.save_prices(
            "area",
            "2023-01-01",
            [PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 10.0)],
        )

        # Re-saving replaces cached data instead of crashing on unique constraint
        repo.save_prices(
            "area",
            "2023-01-01",
            [PricePoint(datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc), 15.0)],
        )

        loaded = repo.load_prices("area", "2023-01-01")
        assert len(loaded) == 1
        assert loaded[0].price == 15.0
