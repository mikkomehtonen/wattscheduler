from fastapi import FastAPI
from wattscheduler.app.api.routes_health import router as health_router
from wattscheduler.app.api.routes_schedule import router as schedule_router
from wattscheduler.app.api.routes_prices import router as prices_router

app = FastAPI()

# Include all routers
app.include_router(health_router)
app.include_router(schedule_router)
app.include_router(prices_router)
