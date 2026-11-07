"""Operational situational alert system for Turku Energia shift supervisors (Level 2).

Identifies high and low price spike risks, regulation regime shifts,
and generates actionable operational recommendations.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


HIGH_SPIKE_THRESHOLD = 0.20
HIGH_SPIKE_CRITICAL = 0.35
LOW_SPIKE_THRESHOLD = 0.20
LOW_SPIKE_CRITICAL = 0.35

RECOMMENDATION_HIGH_SPIKE = (
    "Review thermal dispatch plan; prepare quick-start reserve capacity or reduce flexible consumption."
)
RECOMMENDATION_LOW_SPIKE = (
    "Downward regulation dominant; evaluate curtailing high-cost units or scheduling demand response / storage charging."
)
RECOMMENDATION_REGIME_UP = (
    "Strong upward balancing trend; offer flexible capacity to mFRR upward reserve market."
)
RECOMMENDATION_REGIME_DOWN = (
    "Strong downward balancing trend; evaluate downward reserve bids or flexible demand shifting."
)


def evaluate_origin_alerts(orig_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Evaluate operational situational alerts for a single forecast origin (40 quarter-hours)."""
    if orig_df.empty:
        return []

    alerts: list[dict[str, Any]] = []
    df = orig_df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df["delivery_start_utc"]):
        df["delivery_start_utc"] = pd.to_datetime(df["delivery_start_utc"], utc=True)
    if not pd.api.types.is_datetime64_any_dtype(df["forecast_origin_utc"]):
        df["forecast_origin_utc"] = pd.to_datetime(df["forecast_origin_utc"], utc=True)

    orig_ts = df["forecast_origin_utc"].iloc[0]
    orig_str = orig_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(orig_ts, "strftime") else str(orig_ts)

    # 1. High spike risk (price > spot + 50 EUR/MWh)
    high_spikes = df[df["p_spike_high"] > HIGH_SPIKE_THRESHOLD]
    if len(high_spikes) > 0:
        start_t = high_spikes["delivery_start_utc"].min().strftime("%H:%M")
        end_t = high_spikes["delivery_start_utc"].max().strftime("%H:%M")
        max_prob = float(high_spikes["p_spike_high"].max())
        peak_p50 = float(high_spikes["p50"].max())
        drivers = str(high_spikes.iloc[0].get("top_drivers", ""))
        alerts.append({
            "origin_utc": orig_str,
            "type": "HIGH_SPIKE_RISK",
            "severity": "CRITICAL" if max_prob > HIGH_SPIKE_CRITICAL else "HIGH",
            "time_window": f"{start_t} - {end_t} UTC",
            "max_p_spike": round(max_prob, 3),
            "expected_price": round(peak_p50, 2),
            "drivers": drivers,
            "recommendation": RECOMMENDATION_HIGH_SPIKE,
        })

    # 2. Low price spike / downward regulation warning (price < spot - 50 EUR/MWh)
    low_spikes = df[df["p_spike_low"] > LOW_SPIKE_THRESHOLD]
    if len(low_spikes) > 0:
        start_t = low_spikes["delivery_start_utc"].min().strftime("%H:%M")
        end_t = low_spikes["delivery_start_utc"].max().strftime("%H:%M")
        max_prob = float(low_spikes["p_spike_low"].max())
        min_p50 = float(low_spikes["p50"].min())
        drivers = str(low_spikes.iloc[0].get("top_drivers", ""))
        alerts.append({
            "origin_utc": orig_str,
            "type": "LOW_SPIKE_RISK",
            "severity": "CRITICAL" if max_prob > LOW_SPIKE_CRITICAL else "HIGH",
            "time_window": f"{start_t} - {end_t} UTC",
            "max_p_spike": round(max_prob, 3),
            "expected_price": round(min_p50, 2),
            "drivers": drivers,
            "recommendation": RECOMMENDATION_LOW_SPIKE,
        })

    # 3. Overall regime shift across the 10 h horizon
    if "p_up" in df:
        up_share = float(df["p_up"].mean())
        if up_share > 0.55:
            alerts.append({
                "origin_utc": orig_str,
                "type": "REGULATION_REGIME_UP",
                "severity": "MEDIUM",
                "time_window": "Across 10h horizon",
                "max_p_spike": 0.0,
                "expected_price": round(float(df["p50"].mean()), 2),
                "drivers": str(df.iloc[0].get("top_drivers", "")),
                "recommendation": RECOMMENDATION_REGIME_UP,
            })
        elif "p_down" in df:
            down_share = float(df["p_down"].mean())
            if down_share > 0.55:
                alerts.append({
                    "origin_utc": orig_str,
                    "type": "REGULATION_REGIME_DOWN",
                    "severity": "MEDIUM",
                    "time_window": "Across 10h horizon",
                    "max_p_spike": 0.0,
                    "expected_price": round(float(df["p50"].mean()), 2),
                    "drivers": str(df.iloc[0].get("top_drivers", "")),
                    "recommendation": RECOMMENDATION_REGIME_DOWN,
                })

    return alerts


def generate_situational_overview(
    sub_df: pd.DataFrame, recent_origins: int | None = None
) -> list[dict[str, Any]]:
    """Scan forecast origins in sub_df and return list of situational alerts."""
    df = sub_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["delivery_start_utc"]):
        df["delivery_start_utc"] = pd.to_datetime(df["delivery_start_utc"], utc=True)
    if not pd.api.types.is_datetime64_any_dtype(df["forecast_origin_utc"]):
        df["forecast_origin_utc"] = pd.to_datetime(df["forecast_origin_utc"], utc=True)

    all_origins = df["forecast_origin_utc"].drop_duplicates().sort_values()
    if recent_origins is not None:
        target_origins = all_origins.tail(recent_origins)
    else:
        target_origins = all_origins

    alerts: list[dict[str, Any]] = []
    for orig in target_origins:
        orig_data = df[df["forecast_origin_utc"] == orig]
        orig_alerts = evaluate_origin_alerts(orig_data)
        alerts.extend(orig_alerts)

    return alerts
