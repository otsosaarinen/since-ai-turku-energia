"""Baseline of the organiser, ported from starter_package_v1/baseline.ipynb (unchanged logic).

Used only to reproduce the validation baseline (persistence of the latest usable imbalance price
with historical error quantiles). ``rows_available_at`` (the organiser's helper), ``to_utc`` and
``read_long`` are shared with availability.py; ``write_submission`` with evaluate.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .availability import read_long, rows_available_at, to_utc
from .evaluate import write_submission

HORIZON_STEPS = 40
STEP_MINUTES = 15
SPIKE_MARGIN = 50.0
QUANTILE_LOW, QUANTILE_HIGH = 0.10, 0.90


IMBALANCE = "fi_imbalance_price"
DIRECTION = "fi_mfrr_direction"  # Fingrid 369: 1 up, -1 down, 0 none
STEP_OFFSETS = pd.to_timedelta(np.arange(HORIZON_STEPS) * STEP_MINUTES, unit="min")


def series(data: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Rows of one series sorted by timestamp_utc."""
    return data.loc[data["series_id"] == series_id].sort_values("timestamp_utc").reset_index(drop=True)


PERSISTENCE_LOOKBACK = pd.Timedelta(days=3)  # first try a short slice (fast); fall back to all history


def persistence_at(
    imbalance: pd.DataFrame, origin: pd.Timestamp | str, lookback: pd.Timedelta = PERSISTENCE_LOOKBACK
) -> tuple[float, pd.Timestamp] | tuple[None, None]:
    """Latest imbalance price usable at the origin: (value, timestamp_utc) or (None, None).

    imbalance: rows of fi_imbalance_price sorted by timestamp_utc. Only rows with
    timestamp_utc <= origin are passed to rows_available_at() for speed; later rows can never be
    usable at the origin, so the result is the same as with the full data.
    """
    origin = to_utc(origin)
    timestamps = imbalance["timestamp_utc"]
    lo = timestamps.searchsorted(origin - lookback)
    hi = timestamps.searchsorted(origin, side="right")
    for part in (imbalance.iloc[lo:hi], imbalance.iloc[:hi]):
        wide = rows_available_at(part, origin)
        if IMBALANCE in wide and wide[IMBALANCE].notna().any():
            usable = wide[IMBALANCE].dropna()
            return float(usable.iloc[-1]), usable.index[-1]
    return None, None


def calibrate(
    inputs: pd.DataFrame,
    spot: pd.DataFrame | None,
    first_origin: pd.Timestamp | str,
    *,
    spike_margin: float = SPIKE_MARGIN,
    horizon_steps: int = HORIZON_STEPS,
) -> dict:
    """Historical error quantiles and probabilities for the baseline.

    Leakage rule: only rows and (origin, target) pairs whose first_usable_origin_utc is at or
    before first_origin (the first forecast origin of the period) are used. The persistence start
    value of each historical origin is chosen with rows_available_at(), as in the forecast.
    """
    limit = to_utc(first_origin)
    offsets = STEP_OFFSETS[:horizon_steps]
    imbalance = series(inputs, IMBALANCE)
    known = imbalance.loc[imbalance["first_usable_origin_utc"] <= limit]
    target = known.set_index("timestamp_utc")["value"]
    target_fu = known.set_index("timestamp_utc")["first_usable_origin_utc"]

    errors, used_targets = [], set()
    first_hour = imbalance["timestamp_utc"].min().ceil("h")
    for origin in pd.date_range(first_hour, limit, freq="h"):
        value, _ = persistence_at(imbalance, origin)
        if value is None:
            continue
        deliveries = origin + offsets
        actual = target.reindex(deliveries).to_numpy(dtype=float)
        if np.isnan(actual).all():
            continue
        errors.append(actual - value)
        used_targets.update(deliveries[~np.isnan(actual)])
    err = np.vstack(errors)
    q10 = np.nanquantile(err, QUANTILE_LOW, axis=0)
    q90 = np.nanquantile(err, QUANTILE_HIGH, axis=0)

    direction = series(inputs, DIRECTION)
    direction = direction.loc[(direction["first_usable_origin_utc"] <= limit) & direction["value"].notna()]
    p_up = round(float((direction["value"] == 1).mean()), 6)
    p_down = round(float((direction["value"] == -1).mean()), 6)
    p_none = round(1.0 - p_up - p_down, 6)

    used_fu = [target_fu.loc[sorted(used_targets)].max(), direction["first_usable_origin_utc"].max()]
    if spot is not None and len(spot):
        usable_spot = spot.loc[
            spot["first_usable_origin_utc"] <= limit, ["timestamp_utc", "value", "first_usable_origin_utc"]
        ]
        both = known[["timestamp_utc", "value"]].merge(usable_spot, on="timestamp_utc", suffixes=("_imb", "_spot"))
        both = both.dropna(subset=["value_imb", "value_spot"])
        p_high = round(float((both["value_imb"] > both["value_spot"] + spike_margin).mean()), 6)
        p_low = round(float((both["value_imb"] < both["value_spot"] - spike_margin).mean()), 6)
        n_spike = len(both)
        used_fu.append(both["first_usable_origin_utc"].max())
    else:
        p_high = p_low = 0.0
        n_spike = 0

    return {
        "first_origin": limit,
        "q10": q10,
        "q90": q90,
        "p_up": p_up,
        "p_down": p_down,
        "p_none": p_none,
        "p_spike_high": p_high,
        "p_spike_low": p_low,
        "spot_available": n_spike > 0,
        "n_origins": len(errors),
        "n_error_pairs": int(np.isfinite(err).sum()),
        "n_direction_rows": len(direction),
        "n_spike_rows": n_spike,
        "last_target_used": max(used_targets),
        "max_first_usable_used": max(used_fu),
    }


def build_forecast(
    inputs: pd.DataFrame, cal: dict, origins: pd.Series, horizon_steps: int = HORIZON_STEPS
) -> pd.DataFrame:
    """Baseline submission rows for the given forecast origins (UTC)."""
    imbalance = series(inputs, IMBALANCE)
    offsets = STEP_OFFSETS[:horizon_steps]
    low = np.minimum(cal["q10"][:horizon_steps], 0.0)  # keeps p10 <= p50
    high = np.maximum(cal["q90"][:horizon_steps], 0.0)  # keeps p50 <= p90
    parts = []
    for origin in origins:
        value, ts = persistence_at(imbalance, origin)
        if value is None:
            raise ValueError(f"no usable imbalance price at {origin}")
        p50 = round(value, 4)
        parts.append(
            pd.DataFrame(
                {
                    "forecast_origin_utc": origin,
                    "delivery_start_utc": origin + offsets,
                    "step": np.arange(1, horizon_steps + 1),
                    "p10": np.round(p50 + low, 4),
                    "p50": p50,
                    "p90": np.round(p50 + high, 4),
                    "p_up": cal["p_up"],
                    "p_down": cal["p_down"],
                    "p_none": cal["p_none"],
                    "p_spike_high": cal["p_spike_high"],
                    "p_spike_low": cal["p_spike_low"],
                    "data_cutoff_utc": ts,
                    "top_drivers": "last_imbalance_price",
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def read_origins(path: Path) -> pd.Series:
    """Forecast origins (UTC) from an organiser template file."""
    return pd.to_datetime(pd.read_csv(path)["forecast_origin_utc"], utc=True)


def describe_calibration(cal: dict) -> None:
    """Print what the calibration used (and assert nothing after the limit was touched)."""
    print(f"Calibration limit (first origin of the period): {cal['first_origin']:%Y-%m-%dT%H:%M:%SZ}")
    print(
        f"  historical origins {cal['n_origins']}, error pairs {cal['n_error_pairs']}, "
        f"last target used {cal['last_target_used']:%Y-%m-%dT%H:%M:%SZ}"
    )
    print(f"  latest first_usable_origin_utc used: {cal['max_first_usable_used']:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  p10 offset, steps 1/20/40: {cal['q10'][0]:.2f} / {cal['q10'][19]:.2f} / {cal['q10'][39]:.2f} EUR/MWh")
    print(f"  p90 offset, steps 1/20/40: {cal['q90'][0]:.2f} / {cal['q90'][19]:.2f} / {cal['q90'][39]:.2f} EUR/MWh")
    print(
        f"  direction shares up/down/none: {cal['p_up']:.4f} / {cal['p_down']:.4f} / {cal['p_none']:.4f} "
        f"({cal['n_direction_rows']} rows)"
    )
    if cal["spot_available"]:
        print(
            f"  exceptional price shares high/low: {cal['p_spike_high']:.4f} / {cal['p_spike_low']:.4f} "
            f"({cal['n_spike_rows']} quarter-hours)"
        )
    else:
        print("  WARNING: no spot price data: p_spike_high = p_spike_low = 0.")
    assert cal["max_first_usable_used"] <= cal["first_origin"], "leakage: data after the limit was used"


def run_validation_baseline(
    package_dir: str | Path,
    data_dir: str | Path,
    out_dir: str | Path,
    first_origin: str = "2026-09-06T21:00:00Z",
    days: tuple[str, str] = ("2026-09-07", "2026-10-04"),
    with_spot: bool = True,
) -> tuple[Path, dict]:
    """Reproduce the organiser's validation baseline into out_dir (our own folder).

    Returns the path of the written forecast. make_templates.py is run from the read-only
    starter package with its output pointed to out_dir.
    """
    package_dir, data_dir, out_dir = Path(package_dir), Path(data_dir), Path(out_dir)
    inputs = read_long(data_dir / "inputs.parquet")
    spot = read_long(data_dir / "spot_nordpool.csv") if with_spot else None
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(package_dir / "make_templates.py"),
            "--test-start",
            days[0],
            "--test-end",
            days[1],
            "--output-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
    )
    cal = calibrate(inputs, spot, first_origin)
    origins = read_origins(out_dir / "forecast_origins.csv")
    fc = build_forecast(inputs, cal, origins)
    path = out_dir / "forecast_backtest.csv"
    write_submission(fc, path, out_dir / "sample_submission.csv")
    return path, cal
