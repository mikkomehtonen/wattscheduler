# Default price range end: through end of next day

## Context

The browser UI currently defaults the price range end to `start + 24h` (`app.js:10-11`) — an arbitrary rolling 24-hour window that ends at an odd wall-clock time and often extends past the last published price. Users want a calendar-aligned default: see prices through the end of the next day, or through the end of the current day when next-day prices are not yet published (Spot-Hinta publishes the next Helsinki day in the mid-afternoon; the exact publication time is not encoded anywhere in this repo, so availability must be probed, not guessed).

## Out of Scope

- No API changes: `GET /v1/prices` and `POST /v1/schedule` keep requiring explicit `start`/`end` / `earliest_start`/`latest_end`. The default is a UI concern only.
- No new backend endpoint exposing price availability.
- The default **start** is unchanged (now, rounded up to the next 15-minute boundary, `app.js:5-8`).
- No time-of-day heuristic for publication time (e.g. "assume published after 14:15") — explicitly rejected in favor of a data-driven probe.
- No changes to `CachedPriceProvider` cache semantics (empty-bucket retry behavior stays as-is).

## Implementation approach

**New pure helper file** `src/wattscheduler/app/ui/static/price_range_defaults.js`, following the existing `chart_axis.js` dual-export pattern (`window` global + `module.exports`, see `chart_axis.js:15-16`) so it is importable by Node's built-in `node:test` runner. Five pure functions:

1. `computeDefaultStart(now)` — extract of the existing logic (`app.js:5-8`): zero seconds/ms, round minutes up to the next 15-minute boundary (`Math.ceil(m / 15) * 15`, JS `setMinutes` handles the hour rollover). Behavior identical to today.
2. `endOfDay(d)` — local wall-clock 23:45:00.000 of `d`'s local day: `new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 45, 0, 0)`. The `Date` constructor's local-time normalization makes this DST-safe (on a changeover day the wall-clock 23:45 still exists).
3. `computeDefaultEnd(now, nextDayAvailable)` — `endOfDay(now + 1 local day)` when `nextDayAvailable` is true, else `endOfDay(now)`. Clamp: if the result is earlier than `computeDefaultStart(now)` (e.g. 23:50 with no next-day prices), return `computeDefaultStart(now)` so the range is never inverted and never earlier than the start picker's value or the end picker's `minDate` (`now`, `app.js:23-31`).
4. `nextDayProbeRange(now)` — `{ start: new Date(y, m, d + 1, 0, 0, 0, 0), end: new Date(y, m, d + 1, 23, 45, 0, 0) }` (local), i.e. the full next local day.
5. `nextDayPricesAvailable(payload)` — `Array.isArray(payload) && payload.length > 0`.

**Why 23:45 and not midnight:** price slots are timestamped at their start (last slot of a Helsinki day is 23:45), and `CachedPriceProvider.get_prices`'s final user-facing filter is inclusive on both ends (`price_providers.py:106`). An end of 23:45 includes exactly the last slot of the day; a midnight end would read as the following day in the picker and (being inclusive) could pull in the next day's 00:00 slot.

**Wiring in `app.js` (replaces `app.js:10-11`):**

- On `DOMContentLoaded`, initialize pickers as today, but `latestPicker`'s provisional `defaultDate` is `computeDefaultEnd(now, false)` (end of current day — the safe fallback).
- Then fire one probe request: `fetch('/v1/prices?start=' + range.start.toISOString() + '&end=' + range.end.toISOString())` with `range = nextDayProbeRange(now)`. Values are UTC-aware ISO strings, same as the existing fetch (`app.js:71-72, 79`); no `timezone` param needed.
- If the response is OK and `nextDayPricesAvailable(json)` is true, update the end picker with `latestPicker.setDate(computeDefaultEnd(now, true), false)` (no event fired).
- On any probe failure (network error, non-2xx, malformed payload) leave the provisional end-of-current-day default. No user interaction is possible before the probe resolves, so the update is unconditional.

**`index.html`** (`src/wattscheduler/app/ui/templates/index.html:47-48`): add `<script src="/static/price_range_defaults.js"></script>` **before** the `app.js` script tag, matching the `chart_axis.js` include.

No backend, migration, or dependency changes.

## Tasks

### Task 1 - Pure default-range helper

- `now = 10:07:33.500` local + `computeDefaultStart(now)`
  - → returns same day 10:15:00.000 (seconds/ms zeroed, minutes rounded up)
- `now` exactly on a 15-minute boundary (10:15:00.000) + `computeDefaultStart(now)`
  - → returns 10:15:00.000 unchanged
- `now = 10:50` local + `computeDefaultStart(now)`
  - → returns 11:00:00.000 (hour rollover)
- any date + `endOfDay(d)`
  - → returns 23:45:00.000 of that same local day
- `nextDayAvailable = true` + `computeDefaultEnd(now, true)`
  - → returns next local day 23:45:00.000
- `nextDayAvailable = false` + `computeDefaultEnd(now, false)`
  - → returns current local day 23:45:00.000
- `now = 23:50` local, `nextDayAvailable = false` + `computeDefaultEnd(now, false)`
  - → returned end equals `computeDefaultStart(now)` (clamped; never earlier than start)
- `TZ=Europe/Helsinki`, `now = 2026-10-24 23:50` (DST changeover falls on Oct 25) + `computeDefaultEnd(now, true)`
  - → returns 2026-10-25 23:45 local wall-clock
- any `now` + `nextDayProbeRange(now)`
  - → `{ start: next local day 00:00:00.000, end: next local day 23:45:00.000 }`
- empty array `[]` + `nextDayPricesAvailable([])`
  - → `false`
- array with one price point + `nextDayPricesAvailable(payload)`
  - → `true`
- non-array payload (e.g. `{}` or `null`) + `nextDayPricesAvailable(payload)`
  - → `false`

Tests live in `tests/js/price_range_defaults.test.js` using `node:test`, importing the helper via relative path (pattern: `tests/js/chart_axis.test.js:1-3`); set `process.env.TZ = "Europe/Helsinki"` at the top of the test file before importing the helper.

### Task 2 - Wire probe and picker defaults into the UI

- `GET /static/price_range_defaults.js` via FastAPI `TestClient`
  - → 200 with the helper's JS content
- served index page HTML
  - → contains `<script src="/static/price_range_defaults.js">` positioned before `<script src="/static/app.js">`
- `GET /static/app.js` via `TestClient`, assert on content
  - → contains calls to `computeDefaultStart(`, `computeDefaultEnd(`, `nextDayProbeRange(`, and `nextDayPricesAvailable(`
  - → no longer contains the old `setHours(latest.getHours() + 24)` default-end logic
  - → contains two `fetch(` calls to `/v1/prices` (the existing submit-handler fetch plus the new probe fetch)
  - → contains a `setDate(` call applying the probe result to the latest picker
- full existing suite still passes (`pytest tests/` and `node --test tests/js/*.test.js`, per `scripts/tests.sh`)
  - → no regressions in `tests/js/chart_axis.test.js` or Python tests

Follow the story-005 verification pattern: assert on served static file contents via `TestClient(app)` rather than driving a browser.

## Technical Context

- No new dependencies — plain JS + Node's built-in `node:test` runner (no `npm install`, per `AGENTS.md` "Testing").
- Dual-export pattern to copy: `src/wattscheduler/app/ui/static/chart_axis.js:15-16` (`window.X = X` + `module.exports`).
- Flatpickr instance access in `app.js` is `element._flatpickr` (`app.js:55-56`); programmatic update without firing events is `instance.setDate(date, false)`.
- Backend inclusive end filter: `price_providers.py:106` (`es <= p.timestamp <= le`); note the inner `SpotHintaPriceProvider` uses exclusive end (`spot_hinta_provider.py:69`) but only against full-day bounds, so it does not affect the user-facing edge.
- Price slot timestamps are the slot start; the last slot of a Helsinki day is 23:45 (96 slots/day, 92/100 on DST days — `price_providers.py:65`).
- Existing fetch already sends UTC-aware ISO strings (`app.js:71-72, 79`); the probe follows the same convention, so the `timezone` param (story 001) is not involved.
- JS `Date` constructor local-time arithmetic (`new Date(y, m, d + 1, 23, 45)`) is DST-safe; do not use fixed-ms day arithmetic (`+ 24 * 3600 * 1000`), which drifts across DST transitions.

## Notes

- The probe costs one extra small request per page load. An unpublished probed day leaves an empty cache bucket, which `CachedPriceProvider` refetches on every query that needs it (`price_providers.py:78-87`) — acceptable because when the probe reports unavailable, the UI's default range never includes that day.
- The same two pickers feed both the `/v1/prices` and `/v1/schedule` requests (`app.js:47-113`), so the new default end also bounds the schedule search — intended.
- If "end of current day" (23:45) is already in the past when the page loads (23:45–24:00) and next-day prices are unavailable, the clamp makes start == end (a degenerate, non-inverted range); this window is practically unreachable since next-day prices publish mid-afternoon.
- The end picker's `minDate: now` (`app.js:23-31`) stays as-is; the clamp guarantees the default never violates it.
- No formatter applies to these Markdown/JS files (no Prettier/markdownlint configured in the repo); match the surrounding style.
- Orchestrator decision (2026-10-07, code-review override): the probe's non-empty-array heuristic (partial next-day publication counts as available), the 23:45–24:00 clamp to start, the client-side probe (no server availability endpoint), and unchanged `CachedPriceProvider` empty-bucket semantics are accepted trade-offs — this only sets the end picker's default value, so incomplete next-day data occasionally is not a problem. Do not "fix" these in later passes without a new decision.
