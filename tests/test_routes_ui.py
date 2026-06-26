import re

from fastapi.testclient import TestClient

from wattscheduler.app.main import app

client = TestClient(app)


def test_home_page_has_logo_in_heading():
    resp = client.get("/")
    assert resp.status_code == 200, resp.text

    body = resp.text

    # Heading text is unchanged
    assert "Electricity Scheduler" in body

    # <img> with correct src is inside <h1> and precedes the heading text
    pattern = re.compile(
        r"<h1>\s*<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>\s*Electricity Scheduler\s*</h1>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(body)
    assert match is not None, "Expected <img src='/favicon.svg'> inside <h1> before heading text"

    img_tag = re.search(
        r"<img[^>]+src=\"\s*/favicon\.svg\s*\"[^>]*>",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    assert img_tag is not None
    img_html = img_tag.group(0)

    alt_match = re.search(r'alt=\"([^\"]*)\"', img_html, re.IGNORECASE)
    assert alt_match is not None, "Logo image should have an alt attribute"
    assert alt_match.group(1).strip() != "", "Logo alt attribute should not be empty"


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
