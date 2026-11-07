"""Convert forecast CSVs to compact JSON for the React viewer (web/). No spot prices are exported.
usage: uv run scripts/export_web_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.exports import web_payload  # noqa: E402

OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

for name, src in (("validation", "outputs/validation/backtest_vs_actual.csv"), ("final", "outputs/final/forecast_backtest.csv")):
    payload = web_payload(pd.read_csv(ROOT / src), name)
    (OUT / f"{name}.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(name, len(payload["rows"]), "rows,", round((OUT / f"{name}.json").stat().st_size / 1e6, 1), "MB")
