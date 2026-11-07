#!/bin/bash
# The one command for the whole local setup (Ctrl+C stops everything):
#  1. rebuilds the website's data (web/public/data/) from outputs/ when the model outputs are present,
#  2. starts the control server for the website's Harness panel (http://127.0.0.1:8765),
#  3. starts the website at http://localhost:5173.
# `--data` does only step 1 and exits.
# Step 2 needs a local model server (the Llama app on port 9931 by default; override with LLAMACPP_BASE_URL).
# It lets the website start harness.py runs, which execute model-written Python on this computer: use it only on your own laptop.
set -e
cd "$(dirname "$0")/.."
uv sync --group harness

if [ -f outputs/validation/backtest_vs_actual.csv ] && [ -f outputs/final/forecast_backtest.csv ]; then
  uv run --group harness python - <<'PY'
# Convert forecast CSVs to compact JSON for the React viewer (web/). No spot prices are exported.
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.exports import web_payload
from src.alerts import generate_situational_overview

OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

for name, src in (("validation", "outputs/validation/backtest_vs_actual.csv"), ("final", "outputs/final/forecast_backtest.csv")):
    src_path = ROOT / src
    if src_path.exists():
        df = pd.read_csv(src_path)
        payload = web_payload(df, name)
        (OUT / f"{name}.json").write_text(json.dumps(payload, separators=(",", ":")))
        print(name, len(payload["rows"]), "rows,", round((OUT / f"{name}.json").stat().st_size / 1e6, 1), "MB")

        alerts = generate_situational_overview(df)
        alerts_file = OUT / f"alerts_{name}.json"
        alerts_file.write_text(json.dumps(alerts, indent=2))
        print(f"  -> {len(alerts)} operational alerts exported to {alerts_file.name}")
PY
elif [ -f web/public/data/final.json ] && [ -f web/public/data/validation.json ]; then
  echo "No model outputs here; using the ready-made files in web/public/data/"
else
  echo "Missing forecast data. Get validation.json and final.json from the model owner and put them in web/public/data/." >&2
  exit 1
fi

[ "$1" = "--data" ] && exit 0

[ -d web/node_modules ] || (cd web && npm install --no-audit --no-fund)

uv run --group harness python harness/server.py &  # the Harness panel's control server
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT INT TERM

cd web && npm run dev
