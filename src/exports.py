"""Frontend export: backtest_vs_actual.csv (no spot prices are written)."""
from __future__ import annotations

import numpy as np
import pandas as pd

def backtest_vs_actual(fc: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    a = actuals.rename(columns={"imbalance_price": "actual_imbalance_price", "direction": "actual_direction"})
    a = a.assign(delivery_start_utc=pd.to_datetime(a["delivery_start_utc"], utc=True))
    a["actual_spike_high"] = (a["actual_imbalance_price"] > a["spot_price"] + 50).astype(int)
    a["actual_spike_low"] = (a["actual_imbalance_price"] < a["spot_price"] - 50).astype(int)
    a = a[["delivery_start_utc", "actual_imbalance_price", "actual_direction", "actual_spike_high", "actual_spike_low"]]
    d = fc.assign(delivery_start_utc=pd.to_datetime(fc["delivery_start_utc"], utc=True)).merge(
        a, on="delivery_start_utc", how="left")
    d["abs_error_p50"] = (d["p50"] - d["actual_imbalance_price"]).abs()
    d["inside_p10_p90"] = ((d["actual_imbalance_price"] >= d["p10"]) & (d["actual_imbalance_price"] <= d["p90"])).astype(float)
    d.loc[d["actual_imbalance_price"].isna(), "inside_p10_p90"] = np.nan
    return d
