# Add logo next to page title

## Context

The browser UI's visible page heading is a bare `<h1>Electricity Scheduler</h1>` with no branding. The project already ships a favicon (`src/wattscheduler/app/ui/static/favicon.svg`, a lightning-bolt icon) that is served at `/favicon.svg` by `main.py` and referenced via `<link rel="icon">` in the page `<head>`. Reusing that same asset, place it immediately to the left of the heading text so the top of the page reads `[L] Electricity Scheduler`, while leaving the heading text itself exactly as it is now (same wording, same centered alignment, same font).

## Out of Scope

- Modifying or replacing the `favicon.svg` asset itself.
- Adding the logo to the browser tab `<title>` — only the visible `<h1>` heading changes.
- Restructuring the header into a separate header bar/flex layout; the heading stays a single centered `<h1>` with the logo as inline content.
- Any backend, API, or database changes.

## Implementation approach

Three files change; no new files, no new dependencies, no new static routes (the favicon is already served at `/favicon.svg`).

1. **`src/wattscheduler/app/ui/templates/index.html`** — replace the heading on line 16 with an inline `<img>` before the text, referencing the already-served favicon and carrying an accessibility `alt` and a styling hook class:

   ```html
   <h1><img src="/favicon.svg" alt="Wattscheduler logo" class="title-logo">Electricity Scheduler</h1>
   ```

2. **`src/wattscheduler/app/ui/static/style.css`** — add a rule for `.title-logo` (place it right after the existing `h1` rule block). Sizing the image with `height: 1em` makes it scale with the heading font, including the existing `@media (max-width: 768px)` rule that shrinks `h1` to `1.8rem`. `vertical-align: middle` aligns it to the text baseline, and a small right margin separates it from the text. The existing `h1 { text-align: center }` keeps the logo+text unit centered, so the title remains "as it is now":

   ```css
   .title-logo {
       height: 1em;
       vertical-align: middle;
       margin-right: 0.3em;
   }
   ```

3. **`src/wattscheduler/app/api/routes_ui.py`** — for consistency, update the `FileNotFoundError` fallback `<h1>` (line 22) with the same `<img>`. Because the fallback does not load `style.css`, use inline styles instead of the class:

   ```html
   <h1><img src="/favicon.svg" alt="Wattscheduler logo" style="height: 1em; vertical-align: middle; margin-right: 0.3em">Electricity Scheduler</h1>
   ```

**Tests** — add `tests/test_routes_ui.py` using the existing `TestClient(app)` pattern (see `tests/test_schedule_regression.py`). The conftest already wires `app` and overrides `get_db`. `GET /` reads the template via the relative path `src/wattscheduler/app/ui/templates/index.html`, which resolves correctly when pytest runs from the project root (verified: `GET /` returns 200 with the current `<h1>`). `GET /static/style.css` and `GET /favicon.svg` also return 200.

## Tasks

### Task 1 - Logo markup appears left of the page title

- `GET /` (template file present, normal operation)
  - → response status is 200
  - → response body contains an `<img>` element whose `src` attribute is `/favicon.svg`
  - → that `<img>` is inside the `<h1>` element and appears before the text `Electricity Scheduler` (logo to the left)
  - → the `<h1>` still contains the exact text `Electricity Scheduler`
  - → the `<img>` has a non-empty `alt` attribute

### Task 2 - Logo is styled to align with the title text

- `GET /static/style.css`
  - → response body contains the CSS selector `.title-logo`
  - → the `.title-logo` rule block contains a `height` declaration and a `vertical-align` declaration

## Notes

- The favicon is already served at `/favicon.svg` by `main.py` (`@app.get("/favicon.svg")`); no new static route or asset copy is required.
- The existing `h1 { text-align: center }` rule keeps the logo+text unit centered, preserving the current centered look ("text as it is now").
- The `routes_ui.py` fallback (used only when the template file is missing) is updated with inline-styled `<img>` for consistency; it is not covered by an automated test because triggering it requires the template file to be absent.
- Visual alignment and spacing are verified manually; the automated tests confirm the markup structure and the presence of the CSS rule, not rendered pixels.
