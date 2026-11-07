"""Operational situational alerts for Turku Energia shift supervisors (level 2).

Finds high and low price-spike risks and regulation regime shifts in the forecast and attaches an actionable
recommendation. `generate_situational_overview` is used by scripts/export_web_data.py; its name and signature are fixed.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

HIGH_SPIKE_THRESHOLD = 0.20  # probability of price > spot + 50 EUR/MWh above which a quarter-hour counts
HIGH_SPIKE_CRITICAL = 0.35
LOW_SPIKE_THRESHOLD = 0.20  # probability of price < spot - 50 EUR/MWh
LOW_SPIKE_CRITICAL = 0.35
REGIME_SHARE = 0.55  # average probability of a direction over the horizon above which the whole horizon is flagged
HORIZON_LABEL = "Across 10h horizon"
ORIGIN_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
CLOCK_FORMAT = "%H:%M"

RECOMMENDATION_HIGH_SPIKE = (
    "Review thermal dispatch plan; prepare quick-start reserve capacity or reduce flexible consumption."
)
RECOMMENDATION_LOW_SPIKE = (
    "Downward regulation dominant; evaluate curtailing high-cost units "
    "or scheduling demand response / storage charging."
)
RECOMMENDATION_REGIME_UP = "Strong upward balancing trend; offer flexible capacity to mFRR upward reserve market."
RECOMMENDATION_REGIME_DOWN = (
    "Strong downward balancing trend; evaluate downward reserve bids or flexible demand shifting."
)

Alert = dict[str, Any]


def _with_datetimes(frame: pd.DataFrame) -> pd.DataFrame:
    """A copy whose delivery and origin columns are timestamps (the exports store them as text)."""
    frame = frame.copy()
    for column in ("delivery_start_utc", "forecast_origin_utc"):
        if not pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _drivers(frame: pd.DataFrame) -> str:
    """The top drivers text of the first row ('' when the forecast has none)."""
    return str(frame.iloc[0].get("top_drivers", ""))


def _spike_alert(
    frame: pd.DataFrame,
    origin: str,
    *,
    column: str,
    threshold: float,
    critical: float,
    kind: str,
    recommendation: str,
    use_peak: bool,
) -> Alert | None:
    """An alert when any quarter-hour's spike probability in `column` exceeds `threshold`, else None."""
    risky = frame[frame[column] > threshold]
    if risky.empty:
        return None
    max_probability = float(risky[column].max())
    expected = float(risky["p50"].max() if use_peak else risky["p50"].min())
    return {
        "origin_utc": origin,
        "type": kind,
        "severity": "CRITICAL" if max_probability > critical else "HIGH",
        "time_window": (
            f"{risky['delivery_start_utc'].min().strftime(CLOCK_FORMAT)} - "
            f"{risky['delivery_start_utc'].max().strftime(CLOCK_FORMAT)} UTC"
        ),
        "max_p_spike": round(max_probability, 3),
        "expected_price": round(expected, 2),
        "drivers": _drivers(risky),
        "recommendation": recommendation,
    }


def _regime_alert(frame: pd.DataFrame, origin: str) -> Alert | None:
    """A medium alert when one regulation direction dominates the whole horizon (up is checked first)."""
    if "p_up" not in frame:
        return None
    if float(frame["p_up"].mean()) > REGIME_SHARE:
        kind, recommendation = "REGULATION_REGIME_UP", RECOMMENDATION_REGIME_UP
    elif "p_down" in frame and float(frame["p_down"].mean()) > REGIME_SHARE:
        kind, recommendation = "REGULATION_REGIME_DOWN", RECOMMENDATION_REGIME_DOWN
    else:
        return None
    return {
        "origin_utc": origin,
        "type": kind,
        "severity": "MEDIUM",
        "time_window": HORIZON_LABEL,
        "max_p_spike": 0.0,
        "expected_price": round(float(frame["p50"].mean()), 2),
        "drivers": _drivers(frame),
        "recommendation": recommendation,
    }


def evaluate_origin_alerts(orig_df: pd.DataFrame) -> list[Alert]:
    """Evaluate the alerts of one forecast origin (its 40 quarter-hours)."""
    if orig_df.empty:
        return []
    frame = _with_datetimes(orig_df)
    origin_time = frame["forecast_origin_utc"].iloc[0]
    origin = origin_time.strftime(ORIGIN_FORMAT) if hasattr(origin_time, "strftime") else str(origin_time)
    candidates = (
        _spike_alert(
            frame,
            origin,
            column="p_spike_high",
            threshold=HIGH_SPIKE_THRESHOLD,
            critical=HIGH_SPIKE_CRITICAL,
            kind="HIGH_SPIKE_RISK",
            recommendation=RECOMMENDATION_HIGH_SPIKE,
            use_peak=True,
        ),  # price above spot + 50 EUR/MWh
        _spike_alert(
            frame,
            origin,
            column="p_spike_low",
            threshold=LOW_SPIKE_THRESHOLD,
            critical=LOW_SPIKE_CRITICAL,
            kind="LOW_SPIKE_RISK",
            recommendation=RECOMMENDATION_LOW_SPIKE,
            use_peak=False,
        ),  # price below spot - 50 EUR/MWh: downward regulation warning
        _regime_alert(frame, origin),
    )
    return [alert for alert in candidates if alert is not None]


def generate_situational_overview(sub_df: pd.DataFrame, recent_origins: int | None = None) -> list[Alert]:
    """Scan the forecast origins in sub_df (only the latest `recent_origins` when given) and return all their alerts."""
    frame = _with_datetimes(sub_df)
    origins = frame["forecast_origin_utc"].drop_duplicates().sort_values()
    if recent_origins is not None:
        origins = origins.tail(recent_origins)
    alerts: list[Alert] = []
    for origin in origins:
        alerts.extend(evaluate_origin_alerts(frame[frame["forecast_origin_utc"] == origin]))
    return alerts
