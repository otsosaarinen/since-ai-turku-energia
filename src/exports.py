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


WEB_FC = ["forecast_origin_utc", "delivery_start_utc", "step", "p10", "p50", "p90", "p_up", "p_down", "p_none",
          "p_spike_high", "p_spike_low", "top_drivers"]
WEB_ACT = ["actual_imbalance_price", "actual_direction", "actual_spike_high", "actual_spike_low"]


def web_payload(d: pd.DataFrame, name: str) -> dict:
    """Compact JSON structure read by the web viewer (no spot prices): {name, hasActuals, cols, rows}."""
    d = d.copy()
    cols = WEB_FC + [c for c in WEB_ACT if c in d]
    for c in ("forecast_origin_utc", "delivery_start_utc"):
        d[c] = pd.to_datetime(d[c], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    d = d[cols].round(4).astype(object).where(d[cols].notna(), None)
    return {"name": name, "hasActuals": "actual_imbalance_price" in cols, "cols": cols, "rows": d.values.tolist()}


def quick_metrics(d: pd.DataFrame) -> dict:
    """The five Level-1 metrics from a backtest_vs_actual table (rows without actuals are skipped)."""
    d = d.dropna(subset=["actual_imbalance_price"])
    y = d["actual_imbalance_price"].to_numpy()
    pin = lambda q, a: float(np.mean(np.maximum(a * (y - q), (a - 1) * (y - q))))  # noqa: E731
    pr = np.column_stack([d["p_up"], d["p_down"], d["p_none"]])
    oh = np.column_stack([d["actual_direction"] == "up", d["actual_direction"] == "down", d["actual_direction"] == "none"]).astype(float)
    return {
        "mae": float(np.mean(np.abs(d["p50"] - y))),
        "pinball": (pin(d["p10"].to_numpy(), 0.1) + pin(d["p90"].to_numpy(), 0.9)) / 2,
        "coverage": float(np.mean((y >= d["p10"]) & (y <= d["p90"]))),
        "brier_spike": float((np.mean((d["p_spike_high"] - d["actual_spike_high"]) ** 2)
                              + np.mean((d["p_spike_low"] - d["actual_spike_low"]) ** 2)) / 2),
        "brier_dir": float(np.mean(((pr - oh) ** 2).sum(axis=1))),
    }
