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
        "Expected exactly two fetch calls to /v1/prices (submit handler + probe)"
    )
    assert re.search(r"setDate\(\s*computeDefaultEnd\(", js), (
        "Expected probe result applied to the latest picker via setDate("
    )
    assert re.search(r"setDate\(\s*computeDefaultEnd\([^)]*\),\s*false\s*\)", js), (
        "Expected setDate(..., false) so the probe update does not fire events"
    )
