# Wattscheduler Developer Guidelines

Python project for electricity price based task scheduling using FastAPI, SQLAlchemy (SQLite), and Alembic.

## Build & Development

- **Virtual Environment**: `python -m venv .venv` then `source .venv/bin/activate`.
- **Dependencies**: `pip install -e ".[dev]"` -- the `[dev]` extra contains pytest, ruff, mypy. (README says `.test` but pyproject.toml defines only `[dev]`; trust pyproject.toml.)
- **Development Server**: `python -m uvicorn wattscheduler.app.main:app --reload --port 8080`. Must run from project root -- static files use a relative path (`src/wattscheduler/app/ui/static`).
- **Scripts**: `scripts/run.sh` (port 8081) and `scripts/tests.sh` both set `PYTHONPYCACHEPREFIX=.pycache`.

## Database

- Default SQLite path: `<project_root>/data/wattscheduler.db` (directory auto-created on import). Override via `DATABASE_URL` env var.
- **Migrations**: `alembic revision --autogenerate -m "msg"`, then `alembic upgrade head`.
- Tests use in-memory SQLite with tables created/dropped per-test via conftest -- no alembic needed for tests.

## Testing

- `.venv/bin/python -m pytest tests/ -v` or just `pytest`.
- Single test: `.venv/bin/python -m pytest tests/test_file.py::test_name -v`.
- conftest overrides the `get_db` dependency automatically (autouse fixture). Provides a `db_session` fixture for direct access.

## Linting & Typechecking

- **Ruff**: `ruff check src/ --fix` and `ruff format src/` (line-length: 100).
- **Mypy**: `mypy src/`.

## Architecture

Layers from pure logic to HTTP:

| Layer | Path | Role |
|---|---|---|
| core | `src/wattscheduler/app/core/` | Pure optimizer, models, PriceRepository protocol (ports) |
| infra | `src/wattscheduler/app/infra/` | SQLAlchemy models/repo, price providers (Spot-Hinta + cache) |
| api | `src/wattscheduler/app/api/` | FastAPI routes and dependency wiring (`deps.py`) |
| ui/static | `src/wattscheduler/app/ui/static/` | Frontend assets served via StaticFiles mount at `/static` |

Dependency injection in `api/deps.py` wires: DB session -> SQLAlchemyPriceRepository -> SpotHintaPriceProvider -> CachedPriceProvider.

Entry point: `src/wattscheduler/app/main:app`. Package layout uses `src/` prefix (setuptools `package-dir = {"" = "src"}`).
