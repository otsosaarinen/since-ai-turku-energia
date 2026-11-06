"""Convert forecast CSVs to compact JSON for the React viewer (web/). No spot prices are exported.
usage: uv run scripts/export_web_data.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)
iso = lambda s: pd.to_datetime(s, utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731

FC = ["forecast_origin_utc", "delivery_start_utc", "step", "p10", "p50", "p90", "p_up", "p_down", "p_none",
      "p_spike_high", "p_spike_low", "top_drivers"]
ACT = ["actual_imbalance_price", "actual_direction", "actual_spike_high", "actual_spike_low"]

for name, src in (("validation", "outputs/validation/backtest_vs_actual.csv"), ("final", "outputs/final/forecast_backtest.csv")):
    d = pd.read_csv(ROOT / src)
    cols = FC + [c for c in ACT if c in d]
    for c in ("forecast_origin_utc", "delivery_start_utc"):
        d[c] = iso(d[c])
    d = d[cols].round(4).astype(object).where(d[cols].notna(), None)
    payload = {"name": name, "hasActuals": "actual_imbalance_price" in cols, "cols": cols,
               "rows": d.values.tolist()}
    (OUT / f"{name}.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(name, len(d), "rows,", round((OUT / f"{name}.json").stat().st_size / 1e6, 1), "MB")
