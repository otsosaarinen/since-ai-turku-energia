#!/bin/bash
# Start the forecast viewer at http://localhost:5173 (stop with Ctrl+C). Needs Node.js.
# - On the model owner's machine: rebuilds the viewer data from outputs/ first.
# - On any other machine: uses the ready-made web/public/data/{validation,final}.json
#   (these files are not in git; get them from the model owner).
set -e
cd "$(dirname "$0")/.."
if [ -f outputs/final/forecast_backtest.csv ] && [ -f outputs/validation/backtest_vs_actual.csv ]; then
  uv run scripts/export_web_data.py
elif [ -f web/public/data/final.json ] && [ -f web/public/data/validation.json ]; then
  echo "No model outputs here; using the ready-made files in web/public/data/"
else
  echo "Missing forecast data. Get validation.json and final.json from the model owner and put them in web/public/data/." >&2
  exit 1
fi
cd web
[ -d node_modules ] || npm install --no-audit --no-fund
npm run dev
