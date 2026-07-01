import pathlib

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"


def test_purge_migration_clears_price_points(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "85b2dda37215")  # create table
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO price_points (area, date, timestamp, price) "
                "VALUES ('default','2026-07-01','2026-07-01 20:45:00',0.04553)"
            )
        )
    command.upgrade(cfg, "head")  # run the new purge revision
    with eng.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM price_points")).scalar() == 0
