# Make the heading logo a link driven by LOGO_LINK_URL

## Context

The browser UI heading shows the Wattscheduler logo as a plain, non-clickable `<img>` immediately left of the text `Electricity Scheduler` (added in story 002). Operators want to make that logo clickable so it navigates to a configurable destination (e.g. a marketing site or parent product page), with the target supplied at deploy time via an environment variable. When no target is configured the logo must remain exactly as it is today — a plain, non-clickable image — so existing deployments are unchanged.

## Out of Scope

- Changing the logo asset (`favicon.svg`) or its styling/alignment.
- Making the heading text itself a link; only the logo image is linked.
- Opening the link in a new tab; the link navigates in the same tab (no `target` attribute).
- Adding the logo link anywhere other than the home page heading.
- Any backend/API/database changes beyond reading one env var in the UI route handler.
- New runtime dependencies.

## Implementation approach

Two files change; no new files, no new dependencies, no new routes, and **no change to the template**. The template is served as raw text (read with `open(...).read()` in `routes_ui.py` and returned via `Response`); Jinja2 is not installed (`Jinja2Templates` raises `ImportError`), so the env var is injected with a plain regex substitution in the route handler rather than template rendering.

The logo is the only `<img>` element in the page (the favicon is referenced via a `<link rel="icon">`, not an `<img>`), so the handler can reliably locate it with a regex and wrap it in an `<a>` when the env var is set. This avoids editing the template and avoids any coupling to the exact attribute string or attribute order.

1. **`src/wattscheduler/app/api/routes_ui.py`** — add `import html`, `import os`, and `import re`, plus a module-level helper `_apply_logo_link(markup)` that reads `os.getenv("LOGO_LINK_URL", "").strip()` on every call (per-request, not at import, so tests can drive it with `monkeypatch`):

   - **Env set to a non-empty value** → wrap the first `<img>` whose `src` is `/favicon.svg` in `<a href="{html.escape(url, quote=True)}">...</a>`. The URL is HTML-escaped (`quote=True`) so `&`, `"`, `<`, `>` in the value cannot break the attribute or inject markup. No `target` attribute is added (same-tab navigation). Only the first match is wrapped (`count=1`), which is the logo.
   - **Env unset or whitespace-only** → return the markup unchanged (bare `<img>`, current behavior).

   Apply `_apply_logo_link` to both the template content and the `FileNotFoundError` fallback before returning. The fallback's inline-styled logo `<img>` has the same `src="/favicon.svg"`, so the same regex wraps it. Target state of `routes_ui.py`:

   ```python
   import html
   import os
   import re

   from fastapi import APIRouter, Response

   router = APIRouter()

   _LOGO_IMG_RE = re.compile(r'<img[^>]*src="/favicon\.svg"[^>]*>')


   def _apply_logo_link(markup: str) -> str:
       """Wrap the heading logo <img> in a same-tab link when LOGO_LINK_URL is set.

       The logo is the only <img> with src="/favicon.svg" on the page. When the
       env var holds a non-empty value it is wrapped in <a href="..."> / </a>;
       otherwise the markup is returned unchanged (plain, non-clickable image).
       """
       url = os.getenv("LOGO_LINK_URL", "").strip()
       if not url:
           return markup
       return _LOGO_IMG_RE.sub(
           lambda m: f'<a href="{html.escape(url, quote=True)}">{m.group(0)}</a>',
           markup,
           count=1,
       )


   @router.get("/")
   async def get_home_page():
       """Serve the main HTML page."""
       template_path = "src/wattscheduler/app/ui/templates/index.html"
       try:
           with open(template_path, "r") as f:
               html_content = f.read()
           return Response(content=_apply_logo_link(html_content), media_type="text/html")
       except FileNotFoundError:
           html_content = """
           <!DOCTYPE html>
           <html>
           <head><title>Electricity Scheduler</title></head>
           <body>
               <h1><img src="/favicon.svg" alt="Wattscheduler logo" style="height: 1em; vertical-align: middle; margin-right: 0.3em">Electricity Scheduler</h1>
               <p>Application is running!</p>
           </body>
           </html>
           """
           return Response(content=_apply_logo_link(html_content), media_type="text/html")
   ```

2. **`tests/test_routes_ui.py`** — replace the file with the version below. The conftest already wires `app` and overrides `get_db`; `TestClient(app)` is reused. Because the handler reads the env var per-request, tests control it with `monkeypatch.setenv` / `monkeypatch.delenv`. The existing `test_home_page_has_logo_in_heading` gains `monkeypatch.delenv("LOGO_LINK_URL", raising=False)` so the no-link path is deterministic regardless of the host environment; the existing `test_stylesheet_has_title_logo_rule` is kept unchanged.

   ```python
   import html
   import re

   from fastapi.testclient import TestClient

   from wattscheduler.app.main import app

   client = TestClient(app)


   def test_home_page_has_logo_in_heading(monkeypatch):
       monkeypatch.delenv("LOGO_LINK_URL", raising=False)
       resp = client.get("/")
       assert resp.status_code == 200, resp.text

       body = resp.text
       assert "Electricity Scheduler" in body

       pattern = re.compile(
           r"<h1>\s*<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>\s*Electricity Scheduler\s*</h1>",
           re.IGNORECASE | re.DOTALL,
       )
       assert pattern.search(body) is not None, "Expected bare <img> directly in <h1> when LOGO_LINK_URL is unset"

       img_tag = re.search(r"<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>", body, re.IGNORECASE | re.DOTALL)
       assert img_tag is not None
       alt_match = re.search(r'alt=\"([^\"]*)\"', img_tag.group(0), re.IGNORECASE)
       assert alt_match is not None and alt_match.group(1).strip() != ""


   def test_home_page_logo_is_link_when_env_set(monkeypatch):
       monkeypatch.setenv("LOGO_LINK_URL", "https://example.com")
       resp = client.get("/")
       assert resp.status_code == 200, resp.text

       body = resp.text
       assert "Electricity Scheduler" in body

       pattern = re.compile(
           r"<h1>\s*<a\s+href=\"https://example\.com\">\s*"
           r"<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>\s*</a>\s*Electricity Scheduler\s*</h1>",
           re.IGNORECASE | re.DOTALL,
       )
       assert pattern.search(body) is not None, "Expected <a href> wrapping the logo img inside <h1>"

       a_attrs = re.search(r"<a\s+href=\"https://example\.com\"([^>]*)>", body)
       assert a_attrs is not None
       assert "target" not in a_attrs.group(1).lower(), "Link must navigate in the same tab (no target attribute)"


   def test_home_page_logo_not_link_when_env_whitespace(monkeypatch):
       monkeypatch.setenv("LOGO_LINK_URL", "   ")
       resp = client.get("/")
       assert resp.status_code == 200, resp.text

       body = resp.text
       pattern = re.compile(
           r"<h1>\s*<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>\s*Electricity Scheduler\s*</h1>",
           re.IGNORECASE | re.DOTALL,
       )
       assert pattern.search(body) is not None, "Whitespace-only LOGO_LINK_URL should yield a bare img, no link"


   def test_home_page_logo_link_url_is_html_escaped(monkeypatch):
       raw = 'https://example.com/?a=1&b="2"'
       monkeypatch.setenv("LOGO_LINK_URL", raw)
       resp = client.get("/")
       assert resp.status_code == 200, resp.text

       body = resp.text
       a_match = re.search(r'<a\s+href="([^"]*)"', body)
       assert a_match is not None, "Expected an <a href> tag"
       assert a_match.group(1) == html.escape(raw, quote=True), (
           f"href should be HTML-escaped; got {a_match.group(1)!r}"
       )


   def test_stylesheet_has_title_logo_rule():
       resp = client.get("/static/style.css")
       assert resp.status_code == 200, resp.text

       css = resp.text
       assert ".title-logo" in css

       rule_match = re.search(
           r"\.title-logo\s*\{([^}]*)\}",
           css,
           re.DOTALL,
       )
       assert rule_match is not None, "Expected a .title-logo CSS rule block"
       rule_body = rule_match.group(1)

       assert re.search(r"height\s*:", rule_body) is not None, "Expected height declaration"
       assert re.search(r"vertical-align\s*:", rule_body) is not None, "Expected vertical-align declaration"
   ```

## Tasks

### Task 1 - Logo is a same-tab link when LOGO_LINK_URL is set

- `LOGO_LINK_URL="https://example.com"` + `GET /`
  - → response status is 200
  - → response body contains `<a href="https://example.com">` wrapping the `<img src="/favicon.svg">` logo, inside `<h1>` and before the text `Electricity Scheduler`
  - → the `<a>` has no `target` attribute (same-tab navigation)
  - → the `<h1>` still contains the exact text `Electricity Scheduler`

### Task 2 - Logo stays a plain image when LOGO_LINK_URL is unset or empty

- `LOGO_LINK_URL` unset + `GET /`
  - → response status is 200
  - → response body contains the `<img src="/favicon.svg">` directly inside `<h1>` with no surrounding `<a>` (bare image, current behavior)
  - → the `<h1>` still contains the exact text `Electricity Scheduler`
- `LOGO_LINK_URL="   "` (whitespace only) + `GET /`
  - → response status is 200
  - → response body contains the `<img src="/favicon.svg">` directly inside `<h1>` with no surrounding `<a>` (whitespace treated as unset)

### Task 3 - Logo link URL is HTML-escaped in the href attribute

- `LOGO_LINK_URL='https://example.com/?a=1&b="2"'` + `GET /`
  - → response status is 200
  - → the `<a>` `href` attribute value equals `html.escape('https://example.com/?a=1&b="2"', quote=True)` (i.e. `&` becomes `&amp;` and `"` becomes `&quot;`), so the raw `&` / `"` characters do not appear unescaped inside the attribute

## Notes

- The env var is read inside the handler on each request (`os.getenv`), not at module import, so it can be controlled by tests via `monkeypatch` and changed without restarting the process. This deliberately differs from `DATABASE_URL` in `infra/db.py`, which is read once at import — that pattern would not be testable here.
- `LOGO_LINK_URL` is operator-controlled (an environment variable, not user input); HTML-escaping is applied defensively so a value containing `&` or `"` cannot break the `href` attribute or inject markup.
- The logo is the only `<img>` with `src="/favicon.svg"` on the page; the favicon in `<head>` is a `<link rel="icon">`, so the wrapping regex (`count=1`) targets the heading logo and nothing else. Verified against `index.html`.
- The `FileNotFoundError` fallback in `routes_ui.py` (hit only when the template file is absent) is processed by the same helper for consistency; it is not covered by an automated test because triggering it requires the template file to be missing (same rationale as story 002).
- No CSS changes and no template changes: wrapping an inline `<img>` in an inline `<a>` does not affect the existing centered layout or the `.title-logo` sizing/alignment.
- The existing `test_home_page_has_logo_in_heading` is updated only to add `monkeypatch.delenv("LOGO_LINK_URL", raising=False)`; its assertions (bare `<img>` directly in `<h1>`) remain valid for the unset case.
