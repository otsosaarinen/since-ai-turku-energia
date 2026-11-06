"""Print the forecast for one origin next to the actual price.
usage: uv run scripts/show_origin.py 2026-09-20T09:00   (UTC, validation month 2026-09-06T21:00 .. 2026-10-04T20:00)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
o = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2026-09-20T09:00", tz="UTC")
d = pd.read_csv(ROOT / "outputs/validation/backtest_vs_actual.csv", parse_dates=["forecast_origin_utc", "delivery_start_utc"])
x = d[d.forecast_origin_utc == o]
if x.empty:
    sys.exit(f"no forecast for origin {o}; try a full hour between 2026-09-06T21:00 and 2026-10-04T20:00 UTC")
x = x.assign(time=x.delivery_start_utc.dt.strftime("%H:%M"))
cols = ["step", "time", "p10", "p50", "p90", "actual_imbalance_price", "inside_p10_p90", "p_up", "p_spike_high", "p_spike_low"]
print(f"Origin {o:%Y-%m-%d %H:%M}Z   MAE p50 = {x.abs_error_p50.mean():.1f}   inside p10-p90: {x.inside_p10_p90.mean():.0%}")
print(f"drivers: {x.top_drivers.iloc[0]}")
print(x[cols].round(2).to_string(index=False))
