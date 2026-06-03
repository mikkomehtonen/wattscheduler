import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./wattscheduler.db")

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
        _engine = create_engine(DATABASE_URL, connect_args=connect_args)
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()
