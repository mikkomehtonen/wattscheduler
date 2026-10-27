# Auto-Load the Price Graph on Page Load

## Context

The user opens the UI and almost always presses "Find best schedule" without changing any values, just to see the price graph. Today the graph is rendered only from the submit handler (`app.js:66–132`); on page load the app sets picker defaults and fires the next-day availability probe (`app.js:46–63`, story 006) but draws nothing. Triggering the existing search flow automatically once load completes removes a pointless click and shows the chart immediately.

## Out of Scope

- No backend changes — `/v1/prices` and `/v1/schedule` are untouched.
- No change to the default-range logic from story 006 (probe, `computeDefaultEnd`, next-day extension).
- No de-duplication of the probe fetch and the auto-load price fetch: the probe range is the full next local day (`nextDayProbeRange`) while the search range starts at now, so they are different queries; two `/v1/prices` fetches per load remain.
- No jsdom or browser-level integration tests; DOM behavior in `app.js` is verified via the established source-inspection pattern in `tests/test_routes_ui.py`.

## Implementation approach

- Extract the "Find best schedule" submit-handler body (read pickers/form → fetch `/v1/prices` → POST `/v1/schedule` → `displayResults`) into a named zero-arg function `loadResults()` in `app.js` (currently `app.js:66–132`). The submit handler keeps `preventDefault` and then simply calls `loadResults()` — no behavior change to the manual path.
- In the `DOMContentLoaded` init, attach `.finally(loadResults)` to the end of the existing probe chain (`app.js:46–63`). `.finally` fires on both probe success and probe failure, so the auto-search always runs and always uses the finalized picker defaults (end of next day when prices are published, else end of current day). Ensure a terminal rejection handler (e.g. `.catch`) precedes the `.finally` in the chain so no unhandled rejection escapes and a probe failure cannot skip the auto-search.
- Explicit assumption: the auto-load replicates the full button flow (summary text + chart with best/worst-window highlights), matching the user's "see it without pressing the button" framing — not a chart-only mode.
- State is read at call time, which covers the load-time races:
  - Probe fails (network error, non-2xx, malformed payload) → `.finally` still runs the search with the provisional current-day defaults.
  - User edits pickers while the probe is in flight → the story-006 guard (`app.js:55–58`) keeps the manual selection, and `loadResults()` reads `._flatpickr.selectedDates` at call time, so the user's values win.
  - User presses the button while the auto-search is in flight → last finisher wins; `createChart` already destroys the previous Chart instance (`app.js:171–177`, the "Canvas is already in use -bugi" guard), so double rendering is safe.
  - Auto-search request fails → the single shared `catch` inside `loadResults` shows the existing "Error processing request" in `#summary` (`app.js:128`) and reveals the results card, same as a failed manual search.
- Request budget is unchanged: exactly two `fetch(`/v1/prices` calls in `app.js` (probe + `loadResults`). The existing test `test_app_js_probes_next_day_price_availability` (`tests/test_routes_ui.py:190–200`) asserts this count; the extraction must not introduce a third.

## Tasks

### Task 1 - Extract loadResults() and auto-invoke it after the probe settles

- page load + static inspection of `app.js` source (new source-inspection test in `tests/test_routes_ui.py`, following the pattern of `test_app_js_probes_next_day_price_availability`)
  - → `app.js` contains the extracted routine (regex: `function loadResults\(`)
  - → the submit handler delegates to it (regex over the submit-handler block, e.g. `submit[\s\S]*?loadResults\(\)`)
  - → init auto-invokes it on the probe chain (regex: `\.finally\(\s*loadResults\s*\)`), so it runs after probe success and probe failure alike
- probe failure (fetch throws / malformed payload) + page load
  - → the search still runs with the provisional defaults (guaranteed by the `.finally` wiring asserted above)
- user sets a custom end date before the probe resolves + page load
  - → the story-006 user-selection guard survives the refactor (regex: `selectedDates\[0\]\.getTime\(\) !== latest\.getTime\(\)`)
  - → `loadResults()` reads picker state at call time: the count of `._flatpickr` property reads in `app.js` stays exactly 2 (the two picker reads move into `loadResults`, they are not duplicated)

### Task 2 - Preserve render and error invariants through the refactor

- static inspection of `app.js` after the refactor
  - → still exactly two `fetch\(\s*[`'"]/v1/prices` call sites — the existing test stays green; no third fetch is introduced by the auto-load
  - → the previous-chart destroy guard is preserved (regex: `if \(priceChart\) priceChart\.destroy\(\)`), keeping the auto-load + manual-submit double render free of the Chart.js "Canvas is already in use" bug
  - → the user-facing error string `Error processing request` appears exactly once (its single source is the shared `catch` inside `loadResults`)
- full test suite run (`scripts/tests.sh`)
  - → `pytest tests/` green, including all existing `app.js` source-inspection tests (`tests/test_routes_ui.py:115–200`)
  - → `node --test tests/js/*.test.js` green (no pure-function changes in `price_range_defaults.js` / `chart_axis.js`; regression only)

## Technical Context

- No new dependencies. Chart.js, date-fns, the date-fns Chart.js adapter, and Flatpickr (FI locale) are already loaded via CDN in `src/wattscheduler/app/ui/templates/index.html`; `app.js` needs no new script tags and no reordering (load order is enforced by `tests/test_routes_ui.py:115–127` and `:157–169`).
- `app.js` DOM logic is not testable under `node:test` (no jsdom in this repo); the established way to assert its behavior is source-inspection tests in `tests/test_routes_ui.py` — the regexes above are the contracts the new tests must encode.
- Default form values the auto-search will use: `duration_minutes=30`, `power_kw=2.0` (`templates/index.html:21,24`) and the story-006 picker defaults; none of these change here.
- JS tests need Node ≥ 18 (`node --test`); `scripts/tests.sh` runs pytest then the JS suite.

## Notes

- UX: the results card and chart appear shortly after load — after the probe round-trip plus the search — visually identical to what a manual "Find best schedule" press produces. No loading indicator is added.
- If the Spot-Hinta API is down at page load, the auto-load will surface "Error processing request" without the user clicking anything. This is intentional (consistency with the manual path); suppressing auto-load errors can be revisited if it turns out noisy.
- The probe (`/v1/prices` for the next day) and the auto-search (`/v1/prices` for now→end) stay separate requests; merging them would require changing story-006 semantics and is out of scope.
