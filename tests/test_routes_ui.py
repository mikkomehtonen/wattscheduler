import html
import re

import pytest
from fastapi.testclient import TestClient

from wattscheduler.app.main import app

client = TestClient(app)


@pytest.fixture
def app_js_source():
    resp = client.get("/static/app.js")
    assert resp.status_code == 200, resp.text
    return resp.text


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
    assert pattern.search(body) is not None, (
        "Expected bare <img> directly in <h1> when LOGO_LINK_URL is unset"
    )

    img_tag = re.search(
        r"<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>", body, re.IGNORECASE | re.DOTALL
    )
    assert img_tag is not None
    alt_match = re.search(r"alt=\"([^\"]*)\"", img_tag.group(0), re.IGNORECASE)
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
    assert "target" not in a_attrs.group(1).lower(), (
        "Link must navigate in the same tab (no target attribute)"
    )


def test_home_page_logo_not_link_when_env_whitespace(monkeypatch):
    monkeypatch.setenv("LOGO_LINK_URL", "   ")
    resp = client.get("/")
    assert resp.status_code == 200, resp.text

    body = resp.text
    pattern = re.compile(
        r"<h1>\s*<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>\s*Electricity Scheduler\s*</h1>",
        re.IGNORECASE | re.DOTALL,
    )
    assert pattern.search(body) is not None, (
        "Whitespace-only LOGO_LINK_URL should yield a bare img, no link"
    )


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
    assert re.search(r"vertical-align\s*:", rule_body) is not None, (
        "Expected vertical-align declaration"
    )


def test_home_page_loads_chart_axis_before_app_js(monkeypatch):
    monkeypatch.delenv("LOGO_LINK_URL", raising=False)
    resp = client.get("/")
    assert resp.status_code == 200, resp.text

    body = resp.text
    chart_axis_match = re.search(r'<script\s+src="/static/chart_axis\.js">', body)
    app_js_match = re.search(r'<script\s+src="/static/app\.js">', body)
    assert chart_axis_match is not None, "Expected chart_axis.js script tag"
    assert app_js_match is not None, "Expected app.js script tag"
    assert chart_axis_match.start() < app_js_match.start(), (
        "chart_axis.js must be loaded before app.js"
    )


def test_chart_axis_js_serves_helper():
    resp = client.get("/static/chart_axis.js")
    assert resp.status_code == 200, resp.text
    assert "chooseYAxisDecimals" in resp.text


def test_app_js_uses_dynamic_decimals(app_js_source):
    js = app_js_source
    assert "chooseYAxisDecimals" in js, "Expected app.js to reference chooseYAxisDecimals"
    assert "toFixed(decimals)" in js, "Expected dynamic toFixed(decimals) in Y-axis callback"


def test_price_range_defaults_js_serves_helper():
    resp = client.get("/static/price_range_defaults.js")
    assert resp.status_code == 200, resp.text

    js = resp.text
    for fn in (
        "computeDefaultStart",
        "endOfDay",
        "computeDefaultEnd",
        "nextDayProbeRange",
        "nextDayPricesAvailable",
    ):
        assert f"function {fn}(" in js, f"Expected {fn} in price_range_defaults.js"


def test_home_page_loads_price_range_defaults_before_app_js(monkeypatch):
    monkeypatch.delenv("LOGO_LINK_URL", raising=False)
    resp = client.get("/")
    assert resp.status_code == 200, resp.text

    body = resp.text
    helper_match = re.search(r'<script\s+src="/static/price_range_defaults\.js">', body)
    app_js_match = re.search(r'<script\s+src="/static/app\.js">', body)
    assert helper_match is not None, "Expected price_range_defaults.js script tag"
    assert app_js_match is not None, "Expected app.js script tag"
    assert helper_match.start() < app_js_match.start(), (
        "price_range_defaults.js must be loaded before app.js"
    )


def test_app_js_uses_default_range_helpers(app_js_source):
    js = app_js_source
    for call in (
        "computeDefaultStart(",
        "computeDefaultEnd(",
        "nextDayProbeRange(",
        "nextDayPricesAvailable(",
    ):
        assert call in js, f"Expected app.js to call {call}"


def test_app_js_no_longer_uses_rolling_24h_default_end(app_js_source):
    js = app_js_source
    assert "setHours(latest.getHours() + 24)" not in js, (
        "Old start + 24h default-end logic must be removed"
    )


def test_app_js_probes_next_day_price_availability(app_js_source):
    js = app_js_source
    probe_fetches = re.findall(r"fetch\(\s*[`'\"]/v1/prices", js)
    assert len(probe_fetches) == 2, (
        "Expected exactly two fetch calls to /v1/prices (the search in "
        "loadResults + the next-day probe); the auto-load must not add a third"
    )
    assert re.search(r"setDate\(\s*computeDefaultEnd\(", js), (
        "Expected probe result applied to the latest picker via setDate("
    )
    assert re.search(r"setDate\(\s*computeDefaultEnd\([^)]*\),\s*false\s*\)", js), (
        "Expected setDate(..., false) so the probe update does not fire events"
    )


def test_app_js_auto_loads_results_after_probe_settles(app_js_source):
    js = app_js_source

    assert re.search(r"function loadResults\(", js), (
        "Expected the submit-handler body extracted into loadResults()"
    )

    submit_block = re.search(r"addEventListener\('submit'[\s\S]*?\n\}\);", js)
    assert submit_block is not None, "Expected a submit listener on the schedule form"
    block = submit_block.group(0)
    assert "e.preventDefault()" in block, "Submit handler must keep preventDefault"
    assert re.search(r"loadResults\(\)", block), "Submit handler must delegate to loadResults()"
    assert "fetch(" not in block, (
        "Submit handler body must move into loadResults(); no fetch left inline"
    )

    # Chain composition, not just a substring match: .finally(loadResults)
    # must sit at the END of the probe promise chain (after the picker-
    # extending setDate and the terminal .catch), so the auto-search sees the
    # finalized defaults and a probe rejection cannot skip it. Attaching
    # .finally to the raw fetch instead must fail this test.
    probe_chain = re.search(r"const probeRange[\s\S]*?\.finally\(\s*loadResults\s*\)", js)
    assert probe_chain is not None, (
        "Expected .finally(loadResults) chained onto the probe promise chain"
    )
    chain = probe_chain.group(0)
    assert "setDate(" in chain, (
        "The probe chain must apply the next-day default (setDate) before "
        "handing off to loadResults"
    )
    assert ".catch(" in chain, (
        "A terminal .catch must precede .finally so probe failure still "
        "triggers the auto-search without an unhandled rejection"
    )

    assert re.search(r"selectedDates\[0\]\.getTime\(\) !== latest\.getTime\(\)", js), (
        "Story-006 user-selection guard must survive the refactor"
    )

    assert len(re.findall(r"\._flatpickr", js)) == 2, (
        "Expected exactly two ._flatpickr reads (moved into loadResults, not duplicated)"
    )

    # Overlap sequencing: the auto-load and a manual submit can run
    # concurrently; a superseded run must drop its DOM writes so the newest
    # request wins instead of whichever response lands last.
    assert re.search(r"let searchRunId = 0;", js), "Expected a module-level monotonic run id"
    assert re.search(r"const runId = \+\+searchRunId;", js), (
        "loadResults must claim a run id at call time"
    )
    assert len(re.findall(r"runId !== searchRunId", js)) >= 2, (
        "Both the success render and the error path must drop superseded runs"
    )

    # The auto-load must not pop unprompted modal dialogs on page load;
    # invalid picker state now flows into the shared error card instead.
    assert "alert(" not in js, (
        "No alert() in app.js: the auto-load path must degrade to the "
        "shared error card, not a blocking modal"
    )


def test_app_js_loadResults_never_rejects(app_js_source):
    js = app_js_source

    # .finally(loadResults) adopts loadResults()'s promise; if it could
    # reject (e.g. a picker read throwing), the failure would escape as an
    # unhandled rejection with a blank page. The whole body must sit inside
    # the try so every throw lands in the shared catch and error card.
    assert re.search(r"\.finally\(\s*loadResults\s*\)", js), (
        "Expected .finally(loadResults) on the probe chain"
    )
    body = re.search(r"async function loadResults\(\) \{([\s\S]*?)\n\}\n", js)
    assert body is not None, "Expected the extracted loadResults function"
    body_src = body.group(1)
    try_pos = body_src.find("try {")
    assert try_pos != -1, "Expected loadResults to guard its body with try/catch"
    pre_try = body_src[:try_pos]
    assert pre_try.strip(), "Expected a run-id claim before the try"
    assert "await" not in pre_try and "document." not in pre_try, (
        "Only the run-id claim may precede the try; no fallible read outside it"
    )
    assert body_src.count("catch (") == body_src.count("try {"), (
        "Expected a catch for every try inside loadResults"
    )


def test_app_js_auto_load_preserves_render_and_error_invariants(app_js_source):
    js = app_js_source

    # The two-/v1/prices-fetch budget stays guarded by
    # test_app_js_probes_next_day_price_availability; not duplicated here.
    assert re.search(r"if \(priceChart\) priceChart\.destroy\(\)", js), (
        "Previous-chart destroy guard must be preserved so the auto-load plus a "
        "manual submit cannot hit the Chart.js 'Canvas is already in use' bug"
    )

    assert js.count("Error processing request") == 1, (
        "Expected the error string exactly once, in the shared catch inside loadResults"
    )
