#!/usr/bin/env bash
set -euo pipefail
export PYTHONPYCACHEPREFIX=.pycache
python -m pytest tests -v
