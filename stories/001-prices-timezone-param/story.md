# Add optional `timezone` query parameter to GET /v1/prices

## Context

`GET /v1/prices` accepts `start` and `end` as bare `datetime` query parameters. When a client sends a timestamp **without** an offset (e.g. `2026-02-14T18:00:00`), FastAPI/Pydantic parses it as a *naive* datetime. `SpotHintaPriceProvider.get_prices` then silently treats naive datetimes as UTC (`spot_hinta_provider.py` lines 46-54: `if earliest_start.tzinfo is None: earliest_start = earliest_start.replace(tzinfo=timezone.utc)`).

This is wrong for the product's primary audience: Finnish users who think in local time. A caller writing `start=2026-02-14T00:00:00&end=2026-02-14T23:59:59` intending "Finnish Feb 14" actually receives UTC Feb 14 00:00-23:59, which is Finnish Feb 14 02:00 through Feb 15 01:59 — the wrong day for the first/last two hours, with no way to express intent.

There is currently no mechanism for a client to declare which timezone its naive timestamps are expressed in. This story adds an optional `timezone` query parameter that declares the IANA timezone for interpreting naive `start`/`end` values.

## Out of Scope

- The `POST /v1/schedule` endpoint. It shares `PriceProvider` and has the same naive/aware ambiguity, but it uses a JSON-body DTO (`ScheduleRequestDTO`) with a different parameter style. It is deliberately excluded per the story name (`prices-timezone-param`) and tracked as a known limitation / future story.
- Refactoring the naive/aware bridging logic inside `CachedPriceProvider.get_prices`. The provider already handles tz-aware inputs correctly, so the API-boundary normalization makes the provider receive aware datetimes without needing internal changes.
- Converting returned timestamps to the requested timezone. Output stays UTC (see Implementation approach).
- Accepting fixed UTC offsets (e.g. `+02:00`) or abbreviations (e.g. `EET`). Only IANA names are accepted, for DST correctness and a minimal surface.
- Frontend changes. `app.js` already sends UTC via `toISOString()` and localizes display via `toLocaleTimeString('fi-FI')`; it is unaffected and may optionally send `timezone` in a future story.

## Implementation approach

**Normalization lives at the API boundary, not in the provider.** Add a pure helper in a new module `src/wattscheduler/app/core/timezone_utils.py`:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_utc_if_naive(dt: datetime, tz: ZoneInfo | None) -> datetime:
    """Interpret a naive datetime in `tz` and return it as UTC.

    Aware datetimes are returned unchanged (their offset is authoritative).
    If `tz` is None, the datetime is returned unchanged (legacy behavior).
    """
    if dt.tzinfo is None and tz is not None:
        return dt.replace(tzinfo=tz).astimezone(timezone.utc)
    return dt
```

Placing it in `core` matches the existing layering (pure logic in `core/`, side-effecting wiring in `api/`) and makes it reusable by the schedule endpoint in a future story.

**Route change** in `src/wattscheduler/app/api/routes_prices.py`: add an optional `timezone: str | None = None` query parameter. When provided (i.e. `is not None`, which includes the empty string), construct `ZoneInfo(timezone)` inside a `try`/`except (ZoneInfoNotFoundError, ValueError)` and raise `HTTPException(status_code=400, detail=f"Unknown timezone: {timezone}")` on failure. Catching **both** exceptions is required: unknown IANA names and fixed offsets raise `ZoneInfoNotFoundError`, but the empty string raises `ValueError` ("ZoneInfo keys must be normalized relative paths") — verified empirically against the installed `zoneinfo`. Then call `to_utc_if_naive(start, tz)` and `to_utc_if_naive(end, tz)` before passing to `price_provider.get_prices(...)`. The rest of the handler is unchanged. Do **not** import `datetime.timezone` into this module (the `timezone` parameter name would shadow it); the helper owns the UTC reference.

**Resolution rules (explicit):**

| `start`/`end` form | `timezone` provided | Behavior |
|---|---|---|
| naive | yes (valid IANA) | interpreted in `ZoneInfo(timezone)`, converted to UTC-aware |
| naive | no | returned unchanged (naive) — provider keeps treating naive as UTC (legacy) |
| aware (any offset) | yes or no | returned unchanged — offset is authoritative; `timezone` is ignored for that value |

Why aware inputs are never re-normalized to UTC: `CachedPriceProvider` derives the cache key from `earliest_start.date()` and `earliest_start.tzinfo` (`price_providers.py` lines 39-40, 54-64). Re-normalizing an aware `+02:00` input to UTC would shift its `.date()` and silently change the cache bucket for existing callers. Leaving aware inputs as-is preserves the current cache-key behavior exactly. Naive inputs that get converted become UTC-aware, which feeds the provider's existing, correct aware-datetime path (multi-day UTC iteration in `get_prices`, lines 54-86).

**Output stays UTC.** `PriceResponseDTO.timestamp` continues to serialize the provider's UTC-aware timestamps (unchanged). The frontend already localizes for display; converting server-side would break that contract.

**DST correctness.** `ZoneInfo("Europe/Helsinki")` resolves EET (UTC+2) in winter and EEST (UTC+3) in summer automatically. This is why IANA names are required and fixed offsets are rejected.

**Docker portability.** `zoneinfo` needs timezone data. The dev machine has system tzdata, but the Docker image is `python:3.12-slim` which does **not** ship system tzdata. Add the `tzdata` PyPI package to `pyproject.toml` so `ZoneInfo("Europe/Helsinki")` resolves inside the container without relying on the system.

**No database migration.** `tzdata` is a runtime data library; it adds no schema. No alembic revision is needed.

## Tasks

### Task 1 - Add `tzdata` dependency and `timezone_utils` helper

Precondition: dev venv active. Run `pip install -e ".[dev]"` after editing `pyproject.toml` so the new `tzdata` dependency is installed and `ZoneInfo("Europe/Helsinki")` resolves without system tzdata.

- `pyproject.toml` `[project].dependencies` edited to add `tzdata` (unpinned, matching the existing unpinned style of `fastapi`, `sqlalchemy`, etc.) and `pip install -e ".[dev]"` run
  - → `import tzdata` succeeds (proves the package is installed and available as `zoneinfo`'s fallback data source)
  - → `pip show tzdata` reports the installed package
- new file `src/wattscheduler/app/core/timezone_utils.py` exposing `to_utc_if_naive(dt, tz)`
  - → `import` succeeds and `ruff check` / `mypy src/` are clean
- `to_utc_if_naive(datetime(2026, 2, 14, 0, 0), ZoneInfo("Europe/Helsinki"))` (naive + Helsinki)
  - → returns `datetime(2026, 2, 13, 22, 0, tzinfo=timezone.utc)` (Finnish midnight = previous-day 22:00 UTC, winter EET)
- `to_utc_if_naive(datetime(2026, 7, 14, 0, 0), ZoneInfo("Europe/Helsinki"))` (naive + Helsinki in summer)
  - → returns `datetime(2026, 7, 13, 21, 0, tzinfo=timezone.utc)` (EEST, UTC+3) — proves DST is applied
- `to_utc_if_naive(datetime(2026, 2, 14, 0, 0, tzinfo=ZoneInfo("Europe/Helsinki")), ZoneInfo("Europe/Helsinki"))` (aware + same zone)
  - → returns the input unchanged (aware inputs are not re-normalized); `result == input` and `result.tzinfo` equals the input tzinfo
- `to_utc_if_naive(datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc), ZoneInfo("Europe/Helsinki"))` (aware UTC + a zone)
  - → returns the input unchanged
- `to_utc_if_naive(datetime(2026, 2, 14, 0, 0), None)` (naive + no zone)
  - → returns the input unchanged (legacy path preserved)

### Task 2 - Accept `timezone` query param and map bad values to 400

- `GET /v1/prices?start=2026-02-14T18:00:00&end=2026-02-14T19:00:00&timezone=Not/A/Zone` (unknown IANA)
  - → response status is `400`
  - → response JSON `detail` mentions the offending value (`Not/A/Zone`)
- `GET /v1/prices?start=2026-02-14T18:00:00&end=2026-02-14T19:00:00&timezone=EET` (abbreviation, not IANA)
  - → response status is `400`
- `GET /v1/prices?start=2026-02-14T18:00:00&end=2026-02-14T19:00:00&timezone=%2B02:00` (fixed offset, URL-encoded `+02:00`)
  - → response status is `400`
- `GET /v1/prices?start=2026-02-14T18:00:00&end=2026-02-14T19:00:00&timezone=` (empty string)
  - → response status is `400`

### Task 3 - `timezone` interprets naive `start`/`end`; aware inputs and legacy behavior are preserved

Use `TestClient(app)` with `urllib.request.urlopen` monkeypatched to return Spot-Hinta-shaped mock data (same `MockResponse` / `mock_urlopen` / `monkeypatch` pattern as `tests/test_schedule_regression.py`). **Define a minimal 4-entry mock** in the new test file (do not reuse the wide 21-entry mock from `test_schedule_regression.py`):

```json
[
  {"DateTime": "2026-02-14T18:00:00+02:00", "PriceWithTax": 0.18569},
  {"DateTime": "2026-02-14T18:15:00+02:00", "PriceWithTax": 0.19519},
  {"DateTime": "2026-02-14T18:30:00+02:00", "PriceWithTax": 0.20100},
  {"DateTime": "2026-02-14T18:45:00+02:00", "PriceWithTax": 0.20100}
]
```

These are Finnish 18:00-18:45 (+02:00) = UTC 16:00, 16:15, 16:30, 16:45 on 2026-02-14. The minimal set is required so that the Helsinki interpretation of the naive query (UTC 16:00-17:00) hits the mock while the legacy UTC interpretation (UTC 18:00-19:00) hits nothing — separating the two cases. The query uses `end=19:00` Helsinki (= UTC 17:00); because `CachedPriceProvider` filters with an **inclusive** end boundary (`earliest_start <= p <= latest_end`, `price_providers.py` lines 70-71), a window ending on a slot boundary would include that slot — but the mock has no 17:00 UTC entry, so the result is exactly the 4 entries above.

- naive `start=2026-02-14T18:00:00&end=2026-02-14T19:00:00` + `timezone=Europe/Helsinki`
  - → response status is `200`
  - → response body has 4 price points (UTC 16:00, 16:15, 16:30, 16:45)
  - → first timestamp equals `2026-02-14T16:00:00+00:00`; last equals `2026-02-14T16:45:00+00:00` (output remains UTC-aware)
  - → results are sorted ascending by timestamp
- the same naive `start`/`end` with **no** `timezone` parameter (legacy)
  - → response status is `200`
  - → response body is empty (`[]`), because naive is still treated as UTC and the mock has no entries in the UTC 18:00-19:00 window — proves the new parameter is opt-in and legacy behavior is unchanged
- aware `start=2026-02-14T18:00:00%2B02:00&end=2026-02-14T19:00:00%2B02:00` + `timezone=Europe/Helsinki`
  - → response status is `200`
  - → response body has the same 4 UTC price points as the naive+Helsinki case (offset is authoritative; `timezone` is ignored for aware inputs)
  - → identical to the response of the same aware query **without** the `timezone` parameter (assert the two bodies are equal)
- aware `start=2026-02-14T16:00:00Z&end=2026-02-14T17:00:00Z` + `timezone=Europe/Helsinki`
  - → response status is `200` and returns the same 4 UTC price points (UTC-aware input is not shifted by the timezone parameter)

## Technical Context

- **`tzdata` 2026.2** — latest stable on PyPI (verified via `pip index versions tzdata`). Adds the IANA timezone database for Python's `zoneinfo` module. Required because the Docker base image `python:3.12-slim` ships no system tzdata; without it `ZoneInfo("Europe/Helsinki")` raises `ZoneInfoNotFoundError`. Unpinned in `pyproject.toml` to match the existing dependency style. No breaking changes across tzdata releases (it is a data package).
- **`zoneinfo`** — Python stdlib since 3.9; the project requires `>=3.11` (`pyproject.toml`), so no new dependency is needed for the module itself. Unknown IANA names and fixed offsets raise `zoneinfo.ZoneInfoNotFoundError`; the empty string raises `ValueError` ("ZoneInfo keys must be normalized relative paths"). Both are caught in the route and mapped to `400` (verified empirically against the installed `zoneinfo`).
- **Installed framework versions (for the implementer's awareness; no changes required):** FastAPI 0.136.3, Pydantic 2.13.4, SQLAlchemy 2.0.50. Pydantic v2 parses `2026-02-14T18:00:00` to a naive `datetime` and `2026-02-14T18:00:00+02:00` / `...Z` to an aware one, which is the behavior the resolution rules rely on.
- **HTTP status choice:** invalid `timezone` returns `400` (not FastAPI's default `422`) because the value is semantically invalid, not a type error — the param is a `str` and is validated manually after `ZoneInfo(...)` construction. This makes the error message explicit and testable.
- **Test infrastructure:** `tests/conftest.py` already overrides `get_db` with an in-memory SQLite `StaticPool` and creates/drops tables per test (autouse), so price tests need no extra DB setup. Reuse the `MockResponse` / `mock_urlopen` / `monkeypatch` pattern from `tests/test_schedule_regression.py` to avoid real network calls.

## Notes

- **Explicit assumptions (no interactive question tool was available; please revise any of these):**
  1. `timezone` only affects **naive** `start`/`end`; aware inputs keep their offset and ignore the parameter (no error on the combination). Chosen for backward compatibility and to avoid changing `CachedPriceProvider`'s cache-key derivation.
  2. When `timezone` is **omitted**, behavior is byte-for-byte the legacy behavior (naive treated as UTC by the provider). The parameter is strictly opt-in.
  3. Only **IANA** names are accepted; fixed offsets and abbreviations are rejected with `400`. Chosen for DST correctness (the product is Finnish spot-price based, EET/EEST) and a minimal API surface.
  4. Returned timestamps stay **UTC**; the frontend localizes for display.
- **Cache-key behavior is intentionally unchanged.** `CachedPriceProvider` keys cached prices by the `.date()` of the (post-normalization) `earliest_start` for each iterated day. After this change a naive Helsinki query becomes UTC-aware, so its cache key is the UTC date rather than the local date — this is correct and expected (it reflects the physical window requested). Two callers requesting the same UTC window via different `timezone` values may populate different cache buckets; this is acceptable and not a correctness issue (it is a pre-existing property of the per-query-day cache, not a regression).
- **`POST /v1/schedule` remains naive-as-UTC** for now (same provider, different DTO). Track as a follow-up story if needed.
- **README update recommended (non-automatable):** document the new `timezone` query parameter and the `tzdata` dependency in the "Get Price Data" section. Not covered by an automated test.
