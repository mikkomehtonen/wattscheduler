# Plan: Migrate Cache from File-Based JSON to Relational Database

## 1. Technology Choice

| Component | Recommendation | Rationale |
|---|---|---|
| **Database** | **SQLite** (default) with path to PostgreSQL | SQLite is zero-config and perfect for a single-node cache. If you later need concurrency or external tools, the SQLAlchemy layer makes PostgreSQL a drop-in replacement via `DATABASE_URL`. |
| **ORM / Toolkit** | **SQLAlchemy 2.0** | Industry standard, excellent migration path, and you can use it in a lightweight "Core" style if you want to avoid heavy ORM magic. |
| **Migrations** | **Alembic** | To manage schema changes over time (e.g., adding indexes or new tables). |
| **Async** | **Sync** for now | The current codebase uses synchronous file I/O and `urllib`. Keep it simple: use a standard sync `Session`. You can always upgrade to `asyncpg` / `aiosqlite` later without changing the repository interface. |

**Dependencies to add to `pyproject.toml`:**
```toml
dependencies = [
  ...
  "sqlalchemy",
  "alembic",
]
```

## 2. Target Schema

The current cache stores a list of `(timestamp, price)` per `(area, date)`. A single normalized table is the simplest replacement:

```sql
CREATE TABLE price_points (
    id INTEGER PRIMARY KEY,
    area TEXT NOT NULL,
    date TEXT NOT NULL,          -- YYYY-MM-DD, kept for easy lookup
    timestamp DATETIME NOT NULL,
    price REAL NOT NULL,
    UNIQUE(area, timestamp)
);

CREATE INDEX ix_price_points_lookup ON price_points(area, date);
```

**Why one table?** It maps 1:1 to the current mental model (load by `area` + `date`, filter by time) and avoids unnecessary joins for a simple cache.

## 3. Architecture & Abstraction

Introduce a **Repository Port** so the rest of the app does not depend on SQLAlchemy directly.

1. **Create `app/core/ports.py`** (or similar)
   ```python
   from typing import Protocol, List
   from datetime import datetime
   from wattscheduler.app.core.models import PricePoint

   class PriceRepository(Protocol):
       def load_prices(self, area: str, date_str: str) -> List[PricePoint]: ...
       def save_prices(self, area: str, date_str: str, prices: List[PricePoint]) -> None: ...
   ```

2. **Create `app/infra/db.py`**
   - Engine / `SessionLocal` factory
   - `get_db()` dependency for FastAPI
   - Database URL from environment (default `sqlite:///./wattscheduler.db`)

3. **Create `app/infra/db_models.py`**
   - SQLAlchemy declarative model for `PricePoint` mapping to the table above.

4. **Create `app/infra/repositories.py`**
   - `SQLAlchemyPriceRepository` implementing `load_prices` / `save_prices` using SQLAlchemy sessions.

5. **Refactor `app/infra/price_providers.py`**
   - Change `CachedPriceProvider` to accept a `PriceRepository` instead of `CacheStore`.
   - Delete or deprecate the old `CacheStore`.

6. **Refactor `app/api/routes_schedule.py`**
   - Use FastAPI `Depends` to inject the repository into `get_price_provider()`.
   - Remove the hard-coded `CacheStore("default_cache")` instantiation.

## 4. Step-by-Step Implementation Plan

| Step | Action |
|---|---|
| **1. Dependencies** | Add `sqlalchemy` and `alembic` to `pyproject.toml`. Run `pip install -e ".[dev]"`. |
| **2. DB Setup** | Add `app/infra/db.py` with engine, session factory, and `get_db()` dependency. |
| **3. Model** | Add `app/infra/db_models.py` with the `PricePoint` ORM model. |
| **4. Repository** | Implement `SQLAlchemyPriceRepository` in `app/infra/repositories.py`. |
| **5. Migrate** | Initialize Alembic, generate the first migration script for `price_points`, and run `alembic upgrade head`. |
| **6. Refactor Providers** | Update `CachedPriceProvider` to depend on `PriceRepository`. Remove `CacheStore` imports. |
| **7. Refactor Routes** | Inject the repository via FastAPI `Depends` in `routes_schedule.py`. |
| **8. Tests** | Rewrite `test_cachestore.py` to test `SQLAlchemyPriceRepository` against an in-memory SQLite (`sqlite:///:memory:`). Ensure all other `pytest` tests still pass. |
| **9. Cleanup** | Delete `CacheStore` class, the old `test_cache/` directory, and any leftover file-based cache directories. |
| **10. Documentation** | Update `AGENTS.md` with the new DB setup and Alembic commands. |

## 5. Backward Compatibility & Data Migration

- **No data migration is needed.** The current JSON files are only a **cache**. It is safe to start with an empty database; the app will simply refetch from the Spot-Hinta API on the first request and repopulate the DB.
- Keep the old `CacheStore` code in a git branch or tag if you want a safety net, but remove it from `main` once the DB repository is stable.

## 6. Configuration

Add a `DATABASE_URL` setting (can be as simple as an env var or a Pydantic `BaseSettings` class later):

```bash
# .env (optional)
DATABASE_URL=sqlite:///./wattscheduler.db
```

For CI / tests, override this to `sqlite:///:memory:` in a `pytest` fixture.

## 7. Testing Strategy

- **Unit test the repository:** Use `sqlite:///:memory:` in a fixture so tests are fast and isolated.
- **Integration test the provider:** Ensure `CachedPriceProvider` correctly hits the DB on cache miss and reads from it on cache hit.
- **Regression tests:** Run the existing `test_schedule_regression.py` and `test_main.py` to verify no API behavior changes.

## 8. Optional Future Enhancements

| Enhancement | When to add |
|---|---|
| **Async** (`asyncpg` / `aiosqlite`) | If API latency becomes a concern or you move to an async provider. |
| **Connection pooling** | If switching to PostgreSQL in production. |
| **TTL / eviction** | If the DB grows too large; add a background job to delete price points older than *N* days. |
