#!/bin/bash
# Start the forecast viewer: refresh its data, install packages if needed, run the dev server.
# usage: ./scripts/start_web.sh      (then open http://localhost:5173, stop with Ctrl+C)
set -e
cd "$(dirname "$0")/.."
uv run scripts/export_web_data.py
cd web
[ -d node_modules ] || npm install --no-audit --no-fund
npm run dev
