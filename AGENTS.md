# Wattscheduler Developer Guidelines

Python project for electricity price based task scheduling using FastAPI, SQLAlchemy (SQLite), and Alembic.

## Build & Development

- **Virtual Environment**: `python -m venv .venv` then `source .venv/bin/activate`.
- **Dependencies**: `pip install -e ".[dev]"` -- the `[dev]` extra contains pytest, ruff, mypy. (README says `[test]` but pyproject.toml defines only `[dev]`; trust pyproject.toml.)
- **Development Server**: `python -m uvicorn wattscheduler.app.main:app --reload --port 8080`. Must run from project root -- static files and the `ui/templates/index.html` template are loaded via CWD-relative paths.
- **Scripts**: `scripts/run.sh` (uvicorn, port 8081) and `scripts/tests.sh` both set `PYTHONPYCACHEPREFIX=.pycache`. The root `run.sh` is a `docker run` deploy command, not a dev server.

## Workflow

- Feature work runs through `peck` stories: numbered `stories/NNN-<slug>/` dirs, product overview in `docs/product.md`, custom agents (planner, implementer, explorer, code-reviewer, acceptance-reviewer) in `.opencode/agents/`. Default branch is `master` (`.opencode/peck.json`).
- **Read `docs/learnings.md` before starting work** -- incident log of concrete repo gotchas. Append new learnings after non-trivial tasks (see `.opencode/skills/reflect`); patterns seen twice are promoted into this file. Keep learnings under 15 entries.
- Commits use Conventional Commit prefixes (`feat:`, `fix:`, `chore:`).

## Database

- Default SQLite path: `<project_root>/data/wattscheduler.db` (directory auto-created on import). Override via `DATABASE_URL` env var -- read by both `infra/db.py` and `alembic/env.py`.
- **Migrations**: `alembic revision --autogenerate -m "msg"`, then `alembic upgrade head`.
- The Docker image runs `alembic upgrade head` before starting uvicorn (`Dockerfile` CMD), so container deploys self-migrate; a failed migration aborts startup.
- Tests use in-memory SQLite with tables created/dropped per-test via conftest -- no alembic needed for normal tests. Migration tests drive `alembic.command.upgrade` against a tmp SQLite file with monkeypatched `DATABASE_URL` (see `tests/test_migration_purge_cache.py`).

## Testing

- `.venv/bin/python -m pytest tests/ -v` or just `pytest`. Single test: `pytest tests/test_file.py::test_name -v`.
- conftest overrides the `get_db` dependency automatically (autouse fixture). Provides a `db_session` fixture for direct access.
- **Full suite**: `scripts/tests.sh` runs pytest then `node --test tests/js/*.test.js`. Node.js is required for the JS tests; they use Node's built-in `node:test` runner (no `npm install` needed). The script calls bare `python`, which lacks pytest on this machine, and `source .venv/bin/activate` does not take effect here -- run it as `PATH=.venv/bin:$PATH bash scripts/tests.sh`.
- Single JS test: `node --test tests/js/chart_axis.test.js`. Timezone-sensitive JS tests must set `process.env.TZ = "Europe/Helsinki"` at the top of the file.
- Mock the Spot-Hinta API at the `urllib.request.urlopen` layer (not the provider) to exercise the real `CachedPriceProvider` -> `SpotHintaPriceProvider` stack.
- Parametrize 3+ structurally identical tests with `@pytest.mark.parametrize` -- duplicated test bodies fail code review.

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
| ui | `src/wattscheduler/app/ui/` | `templates/index.html` + `static/` assets served via StaticFiles mount at `/static` |

- Dependency injection in `api/deps.py` wires: DB session -> SQLAlchemyPriceRepository -> SpotHintaPriceProvider -> CachedPriceProvider.
- Entry point: `src/wattscheduler/app/main:app`. Package layout uses `src/` prefix (setuptools `package-dir = {"" = "src"}`).
- **Timezone handling**: Spot-Hinta publishes prices in Europe/Helsinki; storage is UTC. `CachedPriceProvider` caches Helsinki-local calendar-day buckets and must validate completeness (96 slots; 92/100 on DST days) -- the API publishes days incrementally, so non-empty does not mean complete.
- **Frontend**: testable browser logic lives in standalone files under `ui/static/` (e.g. `chart_axis.js`) using an IIFE with dual export (`window.X` and `module.exports`) so the JS tests can `require` them directly; any new module must load before `app.js` in `index.html` (script order is asserted by a test). `tests/test_routes_ui.py` asserts UI wiring by regex-matching the served HTML/`app.js` -- anchor regexes to whole constructs, not bare substrings.
- **Env vars**: `DATABASE_URL` (see Database section); `LOGO_LINK_URL` -- when set, `routes_ui` wraps the heading logo in an `<a>`; passed to the container via `docker run -e LOGO_LINK_URL`.
