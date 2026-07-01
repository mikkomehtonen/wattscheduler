# Fix timezone-related missing hours in the price cache

## Context

The Spot-Hinta API (`https://api.spot-hinta.fi/TodayAndDayForward`) publishes prices organized by **Europe/Helsinki calendar day**. Each entry carries an offset-aware `DateTime` such as `"2026-07-01T00:00:00+03:00"` (EEST, UTC+3 in summer). `SpotHintaPriceProvider` correctly converts each timestamp to UTC before returning it (`spot_hinta_provider.py` lines 62-66). Storing timestamps as UTC is correct and is **not** the bug.

The bug is in `CachedPriceProvider` (`price_providers.py`): it keys each cache bucket by the **UTC date** of the query and fetches a single **UTC-day window** per bucket:

- `_date_str(dt)` returns `dt.date().isoformat()` where `dt` is a UTC midnight datetime (lines 39-40).
- `_get_prices_for_date` fetches `[D 00:00 UTC, D 23:59:59.999999 UTC]` from the inner provider (lines 47-49).
- A Helsinki day does **not** align with a UTC day. In summer (EEST, +3) Helsinki day D spans UTC `[(D-1) 21:00, D 20:45]`. So fetching UTC date D's window keeps only Helsinki D 03:00→23:45 (= UTC D 00:00→20:45, 84 of 96 slots). The Helsinki D+1 00:00→02:45 portion (= UTC D 21:00→23:45, 12 slots) is clipped out of bucket D's window.
- Those 12 clipped slots are only published by the API once Helsinki day D+1 becomes available. But bucket D is never refreshed once non-empty (`if not prices:` at line 46), so the gap is permanent.

Reproduced against the current source: querying UTC `2026-07-01 [00:00, 23:59:59]` while the API has Helsinki Jun 30 + Jul 1 returns 84 points (last `20:45 UTC`); after Helsinki Jul 2 is published, re-querying the same UTC range **still** returns 84 points — the 21:00→23:45 UTC slots are never recovered. This matches the user's database dump exactly (84 rows per UTC date, last timestamp `20:45`).

## Out of Scope

- **Storing timestamps as UTC.** UTC is the correct canonical storage; it is unchanged. Only the cache *bucket boundaries* are wrong.
- **`SpotHintaPriceProvider`.** It already parses offset-aware `DateTime` values and converts to UTC correctly. No change needed.
- **`POST /v1/schedule` naive-as-UTC behavior.** It remains a documented known limitation (see `docs/product.md`, story 001). This story does not add a `timezone` parameter to schedule.
- **The pre-existing unique-constraint discrepancy** between the alembic migration (`uq_area_timestamp` on `area, timestamp`) and the ORM model (`uq_area_date_timestamp` on `area, date, timestamp`). It is unrelated to this bug; Helsinki-day keying satisfies both constraints (each quarter-hour belongs to exactly one Helsinki date, so `(area, timestamp)` stays unique).
- **Frontend.** The UI reads through the API and localizes UTC timestamps for display; no UI change.
- **Making the source timezone configurable via an env var.** The product is Finnish-only (explicit Non-Goal in `docs/product.md`); the source timezone is hardcoded as a constructor default, matching the hardcoded Spot-Hinta URL and `"default"` area in `api/deps.py`.

## Implementation approach

**Align the cache bucket with the API's publication unit.** Key each bucket by the **source-local (Europe/Helsinki) calendar date** and fetch a **full local day** per bucket. A Helsinki day is exactly what the API publishes as a unit, so a full-local-day fetch captures every slot the API has for that day with no UTC-midnight clipping. Once a Helsinki day is published and fetched, its bucket is complete (96 slots, or 92/100 on DST days) and never needs refreshing.

Rewrite `CachedPriceProvider` in `src/wattscheduler/app/infra/price_providers.py` (keep `PriceProvider` and `MockPriceProvider` unchanged):

```python
from datetime import datetime, timezone, timedelta, date as date_cls
from zoneinfo import ZoneInfo

class CachedPriceProvider(PriceProvider):
    def __init__(
        self,
        inner_provider: PriceProvider,
        repository: PriceRepository,
        area: str = "default",
        source_tz: ZoneInfo = ZoneInfo("Europe/Helsinki"),
    ):
        self.inner_provider = inner_provider
        self.repository = repository
        self.area = area
        self.source_tz = source_tz

    def _to_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _get_prices_for_local_date(self, local_date: date_cls) -> List[PricePoint]:
        date_str = local_date.isoformat()
        prices = self.repository.load_prices(self.area, date_str)
        if not prices:
            start_local = datetime(
                local_date.year, local_date.month, local_date.day, 0, 0, tzinfo=self.source_tz
            )
            end_local = start_local + timedelta(days=1)  # half-open [00:00, next 00:00)
            prices = self.inner_provider.get_prices(start_local, end_local)
            self.repository.save_prices(self.area, date_str, prices)
        return prices

    def get_prices(self, earliest_start: datetime, latest_end: datetime) -> List[PricePoint]:
        es = self._to_utc(earliest_start)
        le = self._to_utc(latest_end)
        start_local_date = es.astimezone(self.source_tz).date()
        end_local_date = le.astimezone(self.source_tz).date()
        all_prices: List[PricePoint] = []
        current = start_local_date
        while current <= end_local_date:
            all_prices.extend(self._get_prices_for_local_date(current))
            current += timedelta(days=1)
        filtered = [p for p in all_prices if es <= p.timestamp <= le]
        filtered.sort(key=lambda p: p.timestamp)
        return filtered
```

**Resolution rules (explicit):**

| Input `earliest_start`/`latest_end` | Handling |
|---|---|
| naive | interpreted as UTC (`_to_utc` attaches `timezone.utc`) — preserves the documented legacy behavior (`docs/product.md` Known Limitations) |
| aware (any offset) | converted to UTC via `astimezone(timezone.utc)` |

**Why this fixes the gap.** A UTC query for day D `[D 00:00, D 23:59:59]` converts to Helsinki dates D (from `D 00:00 UTC` = Helsinki D 03:00) and D+1 (from `D 23:59:59 UTC` = Helsinki D+1 02:59). The cache fetches full Helsinki day D (UTC `D-1 21:00 → D 20:45`) and full Helsinki day D+1 (UTC `D 21:00 → D+1 20:45`), then filters the union to `[D 00:00, D 23:59:59] UTC`. Once Helsinki D+1 is published, the D+1 bucket supplies the UTC `D 21:00→23:45` slots that were permanently missing before. Empty buckets (a Helsinki day not yet published) are retried on every query that needs them (the existing `if not prices:` path), so gaps fill in automatically once the API publishes the next day — no manual refresh needed.

**Inclusive end boundary is preserved.** The final filter uses `es <= p.timestamp <= le` (inclusive), matching the existing `CachedPriceProvider` semantics that `test_cached_price_provider_simple` (`tests/test_main.py`) and the `/v1/prices` tests rely on (story 001 notes this explicitly). The inner `SpotHintaPriceProvider` keeps its half-open `< latest_end` filter; with `end_local = start_local + 1 day` and no slot sitting exactly on a local-midnight boundary, the full local day (96/92/100 slots) is captured.

**DST is handled automatically** because the bucket is the local day. Verified with `zoneinfo`: Helsinki 2026-03-29 (spring, EET→EEST, 02:00 skipped) has 92 quarter-hours; Helsinki 2026-10-25 (autumn, EEST→EET, 03:00-03:45 repeated) has 100; a normal summer day has 96. The old UTC-date keying would miscount both DST days.

**No schema change.** The `date` column stays a `String`; only the value written into it changes (Helsinki date instead of UTC date). `db_models.py` is untouched.

**No wiring change.** `api/deps.py` constructs `CachedPriceProvider(real_provider, repo, "default")`; the new `source_tz` parameter defaults to `ZoneInfo("Europe/Helsinki")`, so the existing call works unchanged.

**Purge stale cache via an alembic data migration.** Existing rows are keyed by UTC date (old code); after the fix they are orphaned (the new code never reads them, since it queries Helsinki-date keys). Add an alembic revision (`down_revision = '85b2dda37215'`) whose `upgrade()` runs `op.execute("DELETE FROM price_points")` to purge the stale partial cache so the database repopulates with correct, complete Helsinki-day buckets on the next request. `downgrade()` is a no-op (cache data is not restorable). The cache is regenerable from the API, so a full purge is safe. No new dependency: `alembic` is already in `pyproject.toml`.

## Tasks

### Task 1 - Re-key `CachedPriceProvider` by source-local (Helsinki) date

Precondition: dev venv active (`pip install -e ".[dev]"`). Replace `CachedPriceProvider` as shown in the Implementation approach. Add a new test file `tests/test_cached_price_provider_timezone.py` using the `db_session` fixture (in-memory SQLite, per-test create/drop from `conftest.py`) and `monkeypatch` on `urllib.request.urlopen`, reusing the `MockResponse` pattern from `tests/test_schedule_regression.py`. Use this DST-aware helper to build mock API data and the matching UTC query span for any Helsinki date (it enumerates the UTC quarter-hours that map to the local date, so it is correct on DST days without hardcoding offsets):

```python
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
HKI = ZoneInfo("Europe/Helsinki")

def helsinki_date_entries(y, m, d, base=0.04):
    anchor = datetime(y, m, d, 0, 0, tzinfo=HKI).astimezone(timezone.utc)
    entries, cur, end = [], anchor - timedelta(hours=4), anchor + timedelta(hours=28)
    while cur < end:
        local = cur.astimezone(HKI)
        if (local.year, local.month, local.day) == (y, m, d):
            entries.append({"DateTime": local.isoformat(),
                            "PriceWithTax": round(base + len(entries) * 0.0001, 5)})
        cur += timedelta(minutes=15)
    return entries

def utc_span_for_helsinki_date(y, m, d):
    anchor = datetime(y, m, d, 0, 0, tzinfo=HKI).astimezone(timezone.utc)
    utcs, cur, end = [], anchor - timedelta(hours=4), anchor + timedelta(hours=28)
    while cur < end:
        local = cur.astimezone(HKI)
        if (local.year, local.month, local.day) == (y, m, d):
            utcs.append(cur)
        cur += timedelta(minutes=15)
    return utcs[0], utcs[-1]
```

- API mock returns Helsinki `2026-06-30` + `2026-07-01` data; query UTC `2026-07-01T00:00:00` → `2026-07-01T23:59:59` (aware UTC)
  - → returns 84 price points (Helsinki Jul 2 not yet published, so UTC 21:00→23:45 is unavailable — expected, not a bug)
  - → last timestamp equals `2026-07-01T20:45:00+00:00`; zero points have `hour >= 21`
- then API mock is re-patched to return Helsinki `2026-07-01` + `2026-07-02` data; the **same** UTC `2026-07-01T00:00:00` → `2026-07-01T23:59:59` query is repeated
  - → returns 96 price points (the previously-missing gap is now filled from the Helsinki Jul 2 bucket)
  - → first timestamp equals `2026-07-01T00:00:00+00:00`; last equals `2026-07-01T23:45:00+00:00`
  - → exactly 12 points have `hour >= 21` (the UTC 21:00→23:45 slots)
  - → results are sorted ascending by timestamp
- after the second query, the `price_points` table (query via `db_session.execute(text(...))`) has:
  - → a row group with `date = '2026-07-01'`, count 96, min `timestamp = 2026-06-30 21:00:00`, max `timestamp = 2026-07-01 20:45:00` (a full Helsinki day stored under its Helsinki date, spanning two UTC dates)
  - → a row group with `date = '2026-07-02'`, count 96, min `timestamp = 2026-07-01 21:00:00`, max `timestamp = 2026-07-02 20:45:00`
- API mock returns the DST-aware entries for Helsinki `2026-03-29` (spring forward); query `utc_span_for_helsinki_date(2026, 3, 29)`
  - → returns 92 price points (the 02:00→02:45 local slots do not exist)
  - → the `price_points` table has a single row group `date = '2026-03-29'` with count 92
- API mock returns the DST-aware entries for Helsinki `2026-10-25` (fall back); query `utc_span_for_helsinki_date(2026, 10, 25)`
  - → returns 100 price points (the 03:00→03:45 local hour repeats)
  - → the `price_points` table has a single row group `date = '2026-10-25'` with count 100
  - → both `2026-10-25T00:00:00+00:00` and `2026-10-25T01:00:00+00:00` are present in the returned timestamps (the two distinct UTC slots of the repeated local 03:00 hour)
- full existing suite still passes: `.venv/bin/python -m pytest tests/ -q` is green, `ruff check src/` is clean, `mypy src/` is clean

### Task 2 - Add alembic data migration to purge the stale UTC-date cache

Create the revision with `alembic revision -m "purge stale utc-date price cache"` (no `--autogenerate`; this is a data-only migration). Set `down_revision = '85b2dda37215'` (the existing `create price_points table` revision). Body:

```python
def upgrade() -> None:
    op.execute("DELETE FROM price_points")

def downgrade() -> None:
    # Cache data is regenerable from the Spot-Hinta API and cannot be restored.
    pass
```

Add `tests/test_migration_purge_cache.py` that runs alembic programmatically against a temp SQLite database (verified feasible: `alembic.command.upgrade` works with `alembic.config.Config` pointed at the repo `alembic.ini`, and `env.py` reads `DATABASE_URL` from the environment):

```python
import os, tempfile, pathlib
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"

def test_purge_migration_clears_price_points(monkeypatch):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp}")
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "85b2dda37215")          # create table
    eng = create_engine(f"sqlite:///{tmp}")
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO price_points (area, date, timestamp, price) "
                          "VALUES ('default','2026-07-01','2026-07-01 20:45:00',0.04553)"))
    command.upgrade(cfg, "head")                  # run the new purge revision
    with eng.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM price_points")).scalar() == 0
```

- a temp SQLite DB upgraded to `85b2dda37215` with one stale row inserted, then upgraded to `head`
  - → `SELECT COUNT(*) FROM price_points` is `0` (the purge revision deleted all rows)

## Technical Context

- **No new dependencies.** `zoneinfo` is Python stdlib (project requires `>=3.11`); `tzdata` was added in story 001 so `ZoneInfo("Europe/Helsinki")` resolves inside the `python:3.12-slim` Docker image; `alembic` is already in `pyproject.toml`. Verified the fix passes `ruff check src/`, `mypy src/`, and all 32 existing tests with the prototype applied.
- **Programmatic alembic is feasible.** Confirmed by running `alembic.command.upgrade(Config("alembic.ini"), "85b2dda37215")` against a temp SQLite DB with `DATABASE_URL` set: the existing revision creates the table and a row can be inserted. `alembic.ini` uses `script_location = %(here)s/alembic` and `prepend_sys_path = src`, so a `Config` pointed at the repo `alembic.ini` resolves correctly without extra setup.
- **Real-DB unique constraint.** The existing migration creates `uq_area_timestamp` on `(area, timestamp)` (confirmed via `inspect.get_unique_constraints` on a migrated temp DB). The ORM model instead declares `uq_area_date_timestamp` on `(area, date, timestamp)` — a pre-existing discrepancy, out of scope here. Helsinki-day keying keeps `(area, timestamp)` unique because each quarter-hour maps to exactly one Helsinki date, so a timestamp never appears in two buckets.
- **DST slot counts (verified with `zoneinfo`):** Helsinki `2026-03-29` → 92 quarter-hours (spring forward, 02:00→03:00 EET→EEST); Helsinki `2026-10-25` → 100 quarter-hours (fall back, 04:00 EEST→03:00 EET, the 03:00 hour repeats); a normal summer day → 96. The test helper enumerates UTC quarter-hours mapping to the local date, so it produces exactly these counts and the correct UTC query span without hardcoding offsets (a hardcoded ±3h span would be wrong on the 25-hour autumn day).
- **`SQLAlchemyPriceRepository` is unchanged.** `load_prices`/`save_prices` are keyed by an opaque `date_str`; they do not care whether it is a UTC or Helsinki date. `_utc` in `repositories.py` still attaches UTC to naive timestamps read back from the DB, so loaded `PricePoint`s remain UTC-aware and compare correctly against the UTC-normalized query range.

## Notes

- **Storing UTC is correct; the bug is bucket boundaries.** The fix changes which date string is used as the cache key (Helsinki date instead of UTC date) and the fetch window (full local day instead of a UTC day). Timestamps remain UTC-aware in storage and in responses.
- **Partial results before the next Helsinki day is published are expected, not a bug.** A query for late-UTC hours of day D returns fewer than 96 points until the API publishes Helsinki day D+1 (Spot-Hinta exposes only today + day forward). Once published, the next query fills the gap automatically because empty buckets are retried. This is inherent to the data source, not a defect.
- **Non-empty buckets are not refreshed.** This is intentional and safe: a Helsinki day is published as a complete unit, so a non-empty bucket is complete (96/92/100 slots). Refreshing would add redundant API calls without correcting anything.
- **Manual step after applying the migration to the dev DB:** run `alembic upgrade head` against `data/wattscheduler.db` (or set `DATABASE_URL`) to purge the stale partial rows shown in the bug report; the next request repopulates correct Helsinki-day buckets. The automatable test in Task 2 covers the migration logic; the dev-DB apply is a one-time operational step.
- **`api/deps.py` is intentionally unchanged** — the `source_tz` constructor default applies. Making it explicit would add an import with no behavioral difference.
