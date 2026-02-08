# Wattscheduler

Wattscheduler is a small backend service that helps determine the cheapest time windows to run electricity-consuming tasks based on spot electricity prices.

The project analyzes electricity prices in 15-minute intervals and can answer questions like *“When is the cheapest one-hour window to run the washing machine?”*. It is designed to be simple, testable, and extensible.

The backend is built with **FastAPI** and focuses on clean separation between core optimization logic and HTTP APIs.
