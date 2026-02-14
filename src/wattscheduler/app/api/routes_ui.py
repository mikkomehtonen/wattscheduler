from fastapi import APIRouter, Response
from datetime import datetime, timedelta, timezone
from wattscheduler.app.core.models import PricePoint
from wattscheduler.app.core.optimizer import find_cheapest_windows
from wattscheduler.app.infra.cache import CacheStore
from wattscheduler.app.infra.spot_hinta_provider import SpotHintaPriceProvider
from wattscheduler.app.infra.price_providers import CachedPriceProvider, PriceProvider
from pydantic import BaseModel, Field
from typing import List, Dict, Any

router = APIRouter()


@router.get("/")
async def get_home_page():
    """Serve the main HTML page."""
    # Read the HTML template file
    template_path = "src/wattscheduler/app/ui/templates/index.html"
    try:
        with open(template_path, "r") as f:
            html_content = f.read()
        return Response(content=html_content, media_type="text/html")
    except FileNotFoundError:
        # Fallback to basic HTML if template not found
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Electricity Scheduler</title></head>
        <body>
            <h1>Electricity Scheduler</h1>
            <p>Application is running!</p>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")
