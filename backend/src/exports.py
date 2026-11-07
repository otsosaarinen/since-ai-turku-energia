"""Frontend export: backtest_vs_actual.csv (no spot prices are written)."""

from __future__ import annotations

import numpy as np
import pandas as pd

SPIKE_MARGIN_EUR = 50  # exceptional price = spot +- 50 EUR/MWh (organiser definition)
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
QUANTILE_LOW, QUANTILE_HIGH = 0.1, 0.9


def backtest_vs_actual(fc: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Forecast rows joined with the realised price, direction and spike flags (spot itself is never exported)."""
    actual = actuals.rename(columns={"imbalance_price": "actual_imbalance_price", "direction": "actual_direction"})
    actual = actual.assign(delivery_start_utc=pd.to_datetime(actual["delivery_start_utc"], utc=True))
    price, spot = actual["actual_imbalance_price"], actual["spot_price"]
    actual["actual_spike_high"] = (price > spot + SPIKE_MARGIN_EUR).astype(int)
    actual["actual_spike_low"] = (price < spot - SPIKE_MARGIN_EUR).astype(int)
    actual = actual[
        ["delivery_start_utc", "actual_imbalance_price", "actual_direction", "actual_spike_high", "actual_spike_low"]
    ]
    merged = fc.assign(delivery_start_utc=pd.to_datetime(fc["delivery_start_utc"], utc=True)).merge(
        actual, on="delivery_start_utc", how="left"
    )
    merged["abs_error_p50"] = (merged["p50"] - merged["actual_imbalance_price"]).abs()
    merged["inside_p10_p90"] = (
        (merged["actual_imbalance_price"] >= merged["p10"]) & (merged["actual_imbalance_price"] <= merged["p90"])
    ).astype(float)
    merged.loc[merged["actual_imbalance_price"].isna(), "inside_p10_p90"] = np.nan
    return merged


WEB_FC = [
    "forecast_origin_utc",
    "delivery_start_utc",
    "step",
    "p10",
    "p50",
    "p90",
    "p_up",
    "p_down",
    "p_none",
    "p_spike_high",
    "p_spike_low",
    "top_drivers",
]
WEB_ACT = ["actual_imbalance_price", "actual_direction", "actual_spike_high", "actual_spike_low"]


def web_payload(d: pd.DataFrame, name: str) -> dict:
    """Compact JSON structure read by the web viewer (no spot prices): {name, hasActuals, cols, rows}."""
    d = d.copy()
    cols = WEB_FC + [col for col in WEB_ACT if col in d]
    for col in ("forecast_origin_utc", "delivery_start_utc"):
        d[col] = pd.to_datetime(d[col], utc=True).dt.strftime(TIME_FORMAT)
    d = d[cols].round(4).astype(object).where(d[cols].notna(), None)
    return {"name": name, "hasActuals": "actual_imbalance_price" in cols, "cols": cols, "rows": d.values.tolist()}


def quick_metrics(d: pd.DataFrame) -> dict:
    """The five Level-1 metrics from a backtest_vs_actual table (rows without actuals are skipped)."""
    d = d.dropna(subset=["actual_imbalance_price"])
    y = d["actual_imbalance_price"].to_numpy()

    def pinball(pred: np.ndarray, alpha: float) -> float:
        return float(np.mean(np.maximum(alpha * (y - pred), (alpha - 1) * (y - pred))))

    pr = np.column_stack([d["p_up"], d["p_down"], d["p_none"]])
    oh = np.column_stack(
        [d["actual_direction"] == "up", d["actual_direction"] == "down", d["actual_direction"] == "none"]
    ).astype(float)
    return {
        "mae": float(np.mean(np.abs(d["p50"] - y))),
        "pinball": (pinball(d["p10"].to_numpy(), QUANTILE_LOW) + pinball(d["p90"].to_numpy(), QUANTILE_HIGH)) / 2,
        "coverage": float(np.mean((y >= d["p10"]) & (y <= d["p90"]))),
        "brier_spike": float(
            (
                np.mean((d["p_spike_high"] - d["actual_spike_high"]) ** 2)
                + np.mean((d["p_spike_low"] - d["actual_spike_low"]) ** 2)
            )
            / 2
        ),
        "brier_dir": float(np.mean(((pr - oh) ** 2).sum(axis=1))),
    }
