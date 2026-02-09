#!/usr/bin/env bash
set -euo pipefail
export PYTHONPYCACHEPREFIX=.pycache
cd "$(dirname "$0")/.."
exec .venv/bin/uvicorn wattscheduler.app.main:app --reload --port 8081
