import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker, Session
from wattscheduler.app.infra.db_models import Base
from wattscheduler.app.infra.db import get_db
from wattscheduler.app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def _setup_test_db():
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


def _override_get_db():
    db = _test_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db_session() -> Session:
    session = _test_session_local()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db
