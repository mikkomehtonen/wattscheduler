# Wattscheduler

Wattscheduler is a lightweight electricity scheduling tool that helps
determine the cheapest time windows to run electricity-consuming
appliances based on Finnish spot electricity prices.

The system analyzes electricity prices in **15-minute intervals** and
can answer questions like:

> "When is the cheapest 30-minute window to run the washing machine
> tonight?"

Wattscheduler includes:

-   A cleanly structured FastAPI backend
-   Real-time price fetching from the Finnish Spot-Hinta API
-   Automatic caching of price data
-   An optimization engine for cheapest and most expensive windows
-   A simple browser-based UI with interactive charts
-   Cost estimation based on appliance power (kW)

The project is designed to be simple, testable, and extensible.

------------------------------------------------------------------------

## Features

-   Fetches real electricity prices from https://api.spot-hinta.fi
-   15-minute interval optimization
-   Finds:
    -   Best (cheapest) time window
    -   Worst (most expensive) time window
-   Cost calculation in €/kWh or cents/kWh
-   Interactive bar chart visualization (Chart.js)
-   Frontend time validation (no past start, no invalid ranges)
-   Modular architecture:
    -   `core` -- optimization logic
    -   `infra` -- data providers & caching
    -   `api` -- HTTP routes
    -   `static` -- frontend assets

------------------------------------------------------------------------

## Setup

Create and activate a virtual environment:

    python -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -e .[test]

------------------------------------------------------------------------

## Run the Application

    uvicorn app.main:app --reload --port 8080

------------------------------------------------------------------------

## Open in Browser

-   Web UI: http://localhost:8080/
-   API docs (Swagger): http://localhost:8080/docs
-   Health check: http://localhost:8080/health

------------------------------------------------------------------------

## API Endpoints

### Get Price Data

    GET /v1/prices?start=ISO_DATETIME&end=ISO_DATETIME

Example:

    curl "http://localhost:8080/v1/prices?start=2026-02-14T16:00:00Z&end=2026-02-14T18:00:00Z"

------------------------------------------------------------------------

### Find Best Schedule

    POST /v1/schedule

Example:

    curl -X POST http://localhost:8080/v1/schedule   -H "Content-Type: application/json"   -d '{
        "duration_minutes": 30,
        "power_kw": 2.0,
        "earliest_start": "2026-02-14T18:00:00Z",
        "latest_end": "2026-02-15T06:00:00Z"
      }'

------------------------------------------------------------------------

## Architecture Overview

Wattscheduler follows a clean separation of concerns:

-   **Optimizer** -- Pure logic for calculating cheapest windows
-   **PriceProvider abstraction** -- Allows switching between real and
    mock data
-   **CacheStore** -- Reduces unnecessary external API calls
-   **FastAPI layer** -- HTTP interface
-   **Frontend (static)** -- Chart visualization and scheduling UI

The core optimization logic is completely independent from the HTTP
layer and can be tested in isolation.

------------------------------------------------------------------------

## Running Tests

    pytest

------------------------------------------------------------------------

## License

MIT License
