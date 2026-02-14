from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from wattscheduler.app.api.routes_health import router as health_router
from wattscheduler.app.api.routes_schedule import router as schedule_router
from wattscheduler.app.api.routes_prices import router as prices_router
from wattscheduler.app.api.routes_ui import router as ui_router

app = FastAPI()

# Include all routers
app.include_router(health_router)
app.include_router(schedule_router)
app.include_router(prices_router)
app.include_router(ui_router)

# Serve static files
app.mount("/static", StaticFiles(directory="src/wattscheduler/app/ui/static"), name="static")
