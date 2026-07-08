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


def test_app_js_uses_dynamic_decimals():
    resp = client.get("/static/app.js")
    assert resp.status_code == 200, resp.text

    js = resp.text
    assert "chooseYAxisDecimals" in js, "Expected app.js to reference chooseYAxisDecimals"
    assert "toFixed(decimals)" in js, "Expected dynamic toFixed(decimals) in Y-axis callback"
