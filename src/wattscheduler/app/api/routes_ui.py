from fastapi import APIRouter, Response

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
            <h1><img src="/favicon.svg" alt="Wattscheduler logo" style="height: 1em; vertical-align: middle; margin-right: 0.3em">Electricity Scheduler</h1>
            <p>Application is running!</p>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")
