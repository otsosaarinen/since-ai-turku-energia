#!/bin/bash
# One command to run the whole project on your laptop:   ./dev.sh        (flag: --no-harness)
#   1. rebuilds the website's data files from backend/outputs/ (when the model has been run)
#   2. starts the Harness server (backend) unless it is hidden (NEXT_PUBLIC_HIDE_HARNESS=true in .env) or you pass --no-harness
#   3. starts the website at http://localhost:5173
# Stop everything with Ctrl+C. To use another website port: FRONTEND_PORT=5180 ./dev.sh Needs Node.js and uv; the Harness also needs the Llama app (local model) running.
set -e
cd "$(dirname "$0")"
frontend_port="${FRONTEND_PORT:-5173}"

use_harness=true
[ "$1" = "--no-harness" ] && use_harness=false
if [ -f .env ] && grep -qiE '^[[:space:]]*NEXT_PUBLIC_HIDE_HARNESS=("|'"'"')?(true|1)("|'"'"')?[[:space:]]*$' .env; then use_harness=false; fi

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
for port in "$frontend_port" $($use_harness && echo 8765); do
  if port_busy "$port"; then
    echo "Port $port is already in use (probably an old dev server). Find it: lsof -nP -iTCP:$port -sTCP:LISTEN   then: kill <PID>" >&2
    exit 1
  fi
done

if [ -f backend/outputs/validation/backtest_vs_actual.csv ] && [ -f backend/outputs/final/forecast_backtest.csv ]; then
  (cd backend && uv run python scripts/export_web_data.py)
elif [ ! -f frontend/public/data/final.json ]; then
  echo "Note: no forecast data yet. Run the model (see README) or get frontend/public/data/ from the model owner; the page will say the data is missing." >&2
fi

trap 'trap - EXIT; kill 0' EXIT INT TERM     # stopping this script stops the harness server and the website too
if $use_harness; then
  (cd backend && uv sync --group harness -q && uv run --group harness python -m harness.server) &
fi

cd frontend
[ -d node_modules ] || npm install --no-audit --no-fund
npm run dev -- -p "$frontend_port"
