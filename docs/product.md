# Wattscheduler

Wattscheduler is a lightweight electricity scheduling tool that determines the cheapest time windows to run electricity-consuming appliances based on Finnish spot electricity prices. It analyzes prices in 15-minute intervals and answers questions like "when is the cheapest 30-minute window to run the washing machine tonight?". It is aimed at Finnish household consumers who want to shift flexible loads to low-price hours.

## Features

- **Spot-price fetching** — pulls real 15-minute electricity prices from the Finnish Spot-Hinta API (`https://api.spot-hinta.fi`).
- **Price caching** — SQLite-backed cache (SQLAlchemy) avoids redundant external API calls; cached per area and date.
- **Cheapest / most expensive windows** — pure optimizer finds the cheapest and most expensive contiguous windows for a given duration.
- **Cost estimation** — estimates EUR cost from window price, appliance power (kW), and the 15-minute interval.
- **Schedule API** — `POST /v1/schedule` returns best and worst windows with savings vs. running now.
- **Prices API** — `GET /v1/prices` returns raw price points for a time range.
- **Prices timezone parameter** — `GET /v1/prices` accepts an optional `timezone` query parameter (IANA name) so callers can declare the timezone their naive `start`/`end` are expressed in; naive values are interpreted in that zone and converted to UTC before querying ([story](stories/001-prices-timezone-param/story.md)).
- **Browser UI** — static HTML/JS app with Flatpickr date pickers and a Chart.js bar chart highlighting the best and worst windows. The page heading shows the favicon logo to the left of the title text ([story](stories/002-add-logo-to-title/story.md)).
- **Health check** — `GET /health` for container liveness.
- **Docker** — ships a `Dockerfile` (python:3.12-slim) with a health check.

## Non-Goals

- Not a billing or invoicing system; costs are estimates from spot price + tax, not final invoices.
- Not a real-time appliance controller; it only recommends windows.
- Not a multi-country product; the price source is Finnish (Spot-Hinta) and the UI locale is Finnish.
- Not a historical analytics tool; it focuses on today and the day forward (Spot-Hinta `TodayAndDayForward`).

## Known Limitations

- **Naive timestamps without a `timezone` parameter are treated as UTC.** This is the legacy behavior of `SpotHintaPriceProvider`; callers who mean local time must send an offset or use the new `timezone` parameter.
- **`POST /v1/schedule` does not yet accept a `timezone` parameter.** It shares the price provider with `/v1/prices` and has the same naive/aware ambiguity for `earliest_start`/`latest_end`; a follow-up story is tracked separately.
- **Price cache is keyed by the query day, not a global UTC day.** Requests for the same physical UTC window expressed via different timezones may populate separate cache buckets; this is not a correctness issue but can cause redundant fetches.
- **Fixed UTC offsets and timezone abbreviations are rejected** by the `timezone` parameter; only IANA names (e.g. `Europe/Helsinki`) are accepted, for DST correctness.
- **Spot-Hinta only provides today and day-forward data**; requests beyond that range return no prices.
- **Returned timestamps are always UTC-aware**; the frontend localizes them for display.
