# Chart Y-axis decimal adaptation

## Context

The browser UI's price chart (`src/wattscheduler/app/ui/static/app.js`, `createChart`) formats Y-axis tick labels with a hardcoded `(value * 100).toFixed(0)`, i.e. whole-number snt/kWh. On a day when electricity is cheap for the whole day (e.g. prices ~0.5–1.3 snt/kWh), every Y-axis tick rounds to the same integer (`1`), so the axis shows a column of identical `1`s (or `0`s) and becomes unreadable. The fix: when the 0-decimal labels would collide (duplicates), render 1 decimal place instead. The decimal count is capped at 1 — a hypothetical sub-0.1-snt/kWh-all-day scenario where even 1 decimal collides is accepted as negligibly rare (per product decision).

## Out of Scope

- Changing the Chart.js version or pinning the CDN URL (`index.html` loads `https://cdn.jsdelivr.net/npm/chart.js` unpinned; left as-is).
- Adjusting the X-axis, tooltip, or summary formatting (only the Y-axis tick labels change).
- Any backend, API, database, or Python optimizer change.
- Supporting more than 1 decimal place (cap is 1 by design).
- Rendering-pixel verification of the chart (the wiring is verified structurally; visual check is manual).

## Implementation approach

Six files change; one new static JS file, one new JS test file. No new npm dependencies — JS tests use Node's built-in `node:test` runner (Node v26.4.0 is present in the dev environment).

### Decimal-selection rule (pure, extracted)

The decision logic is extracted into a new pure, Node-safe file `src/wattscheduler/app/ui/static/chart_axis.js` so it can be unit-tested without a browser. The function `chooseYAxisDecimals(tickValues)` takes the Y-axis tick values **in display units (snt/kWh)** and returns the number of decimal places to render:

- Let `T` = the input array (display-space snt/kWh values, i.e. raw EUR/kWh × 100, exactly what the callback renders).
- Build the set of 0-decimal labels `L0 = { Number(t).toFixed(0) for t in T }`.
- If `|L0| < |T|` (any duplicate among the 0-decimal labels) → return `1`.
- Otherwise → return `0`.
- **Cap:** never return more than `1` (the function only ever returns 0 or 1).

Edge cases, all handled by the rule above:
- Empty array `[]` → `0` (guard clause).
- Single tick → `0` (no duplicate possible).
- Negative spot prices: `Number(...).toFixed(0)` produces `"-0"` for negative values that round to zero; `"-0"` and `"0"` are distinct strings, so e.g. `[-0.4, -0.2, 0]` → labels `["-0", "-0", "0"]` → duplicate `"-0"` → returns `1`. Distinct negatives (e.g. `[-1, 0, 1, 2]`) → `0`.
- Cap-at-1: values that collide at 0 decimals **and** would still collide at 1 decimal (e.g. `[0.04, 0.04]`) → returns `1`, never `2`.

The file uses a dual browser/Node export pattern so the same file is loaded by the browser via `<script>` (sets `window.chooseYAxisDecimals`) and `require`d by Node tests (`module.exports`):

```js
(function () {
    "use strict";
    function chooseYAxisDecimals(tickValues) {
        if (!Array.isArray(tickValues) || tickValues.length === 0) return 0;
        var seen = {};
        for (var i = 0; i < tickValues.length; i++) {
            var label = Number(tickValues[i]).toFixed(0);
            if (seen[label]) return 1;
            seen[label] = true;
        }
        return 0;
    }
    if (typeof window !== "undefined") window.chooseYAxisDecimals = chooseYAxisDecimals;
    if (typeof module !== "undefined" && module.exports) module.exports = { chooseYAxisDecimals: chooseYAxisDecimals };
})();
```

### Chart Y-axis wiring (`app.js`)

The Y-axis `ticks.callback` in `createChart` is changed from a hardcoded `.toFixed(0)` to compute decimals from the ticks Chart.js actually generates. Chart.js v4 passes the callback `(tickValue, index, ticks)` where each element of `ticks` is a `Tick` object with a `.value` field (the scale-unit value, EUR/kWh here). The callback converts each tick to display snt/kWh (`t.value * 100`), asks the helper for the decimal count, and formats with it:

```js
ticks: {
    callback: function (value, index, ticks) {
        var sntValues = ticks.map(function (t) { return t.value * 100; });
        var decimals = chooseYAxisDecimals(sntValues);
        return (value * 100).toFixed(decimals);
    }
}
```

`chooseYAxisDecimals` is available as a global because `chart_axis.js` is loaded before `app.js` (see HTML change below). The `ticks` array is identical across all callback invocations within one render, so the computed `decimals` is consistent for every label. Recomputing per tick is O(n²) with n ≈ 5–11 ticks — negligible.

### HTML load order (`index.html`)

Add `<script src="/static/chart_axis.js"></script>` immediately before the existing `<script src="/static/app.js"></script>` (line 47) so the helper global exists before `app.js` runs.

### Test runner integration (`scripts/tests.sh`)

Append `node --test tests/js/*.test.js` after the existing `python -m pytest tests -v` line so the full test suite runs both Python and JS tests. `node:test` and `node:assert/strict` are built into Node ≥ 18; no `npm install` is needed. pytest only collects `test_*.py` files, so the new `tests/js/` directory of `.js` files does not interfere with Python test collection.

## Tasks

### Task 1 - Decimal-selection helper function

Verified by `node --test tests/js/chart_axis.test.js` (file: `tests/js/chart_axis.test.js`, using `node:test` + `node:assert/strict`, requiring `../../src/wattscheduler/app/ui/static/chart_axis.js`).

- distinct 0-decimal labels (e.g. `[0, 5, 10, 15, 20]`) + `chooseYAxisDecimals` called
  - → returns `0`
- colliding 0-decimal labels (e.g. `[0.5, 0.7, 0.9, 1.1, 1.3]`, all round to `"1"`) + called
  - → returns `1`
- empty array `[]` + called
  - → returns `0`
- single value (e.g. `[7]`) + called
  - → returns `0`
- distinct negative values (e.g. `[-1, 0, 1, 2]`) + called
  - → returns `0`
- colliding negative values (e.g. `[-0.4, -0.2, 0]` → labels `["-0", "-0", "0"]`) + called
  - → returns `1`
- values that collide at 0 decimals AND would still collide at 1 decimal (e.g. `[0.04, 0.04]`) + called
  - → returns `1` (never `2`, confirming the cap)

### Task 2 - Chart Y-axis labels use dynamic decimal places

Verified by pytest in `tests/test_routes_ui.py` (existing `TestClient(app)` pattern).

- `GET /` (template present, normal operation)
  - → response body contains `<script src="/static/chart_axis.js">`
  - → that script tag appears before `<script src="/static/app.js">`
- `GET /static/chart_axis.js`
  - → response status is 200
  - → response body contains the identifier `chooseYAxisDecimals`
- `GET /static/app.js`
  - → response status is 200
  - → response body contains `chooseYAxisDecimals` (the Y-axis callback references the helper)
  - → response body contains `toFixed(decimals)` (dynamic decimal count, not a hardcoded literal)

## Technical Context

- **Chart.js** — loaded unpinned from `https://cdn.jsdelivr.net/npm/chart.js` (resolves to latest 4.x). Verified latest stable: **4.5.1** (`npm view chart.js version`). The tick callback contract `(this: Scale, tickValue: number|string, index: number, ticks: Tick[])` where each `Tick` has `.value: number|string` is stable across 4.x (confirmed in the 4.5.1 type definitions: `dist/core/core.scale.d.ts` exports `Tick = { value, label?, major?, $context? }` and `dist/types/index.d.ts` line 3085 declares the callback signature). No CDN pin change in this story.
- **Node.js** — v26.4.0 is installed in the dev environment. `node:test` and `node:assert/strict` are built-in modules (stable since Node 18); no `npm install` or `package.json` is required. JS tests run via `node --test tests/js/*.test.js`.
- No new npm or pip dependencies are introduced.

## Notes

- **Node.js is now required to run the full test suite** (`scripts/tests.sh` runs `pytest` then `node --test`). Contributors who only work on Python may still run `pytest` alone; the JS tests are independent.
- The decimal cap is **1** by product decision. A sub-0.1-snt/kWh-all-day scenario (where even 1-decimal labels could duplicate) is accepted as negligibly rare and will not trigger a 2-decimal fallback.
- `app.js` is browser-coupled (`document`, `flatpickr`, `Chart`, `fetch`) and cannot be `require`d in Node, so only the extracted pure helper is unit-tested in Node; the `app.js` wiring is verified by structural pytest assertions (helper referenced + dynamic `toFixed(decimals)`), not by rendering pixels. Visual confirmation that the cheap-day axis now shows e.g. `0.5, 0.7, 0.9, 1.1` is manual.
- pytest ignores `tests/js/*.js` (default `python_files = test_*.py *_test.py`), so the new JS test directory does not interfere with Python test collection.
- The `routes_ui.py` `FileNotFoundError` fallback HTML does not load `app.js` or `chart_axis.js` (no chart on that page), so it needs no change.
