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
