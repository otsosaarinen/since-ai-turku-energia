"""Feature construction for one forecast origin (40 target quarter-hours).

LEAKAGE CONTRACT
* ``build_origin_features`` receives ONLY an availability-filtered ``Window`` (see
  availability.py): every cell with first_usable_origin_utc > origin is already NaN.
  It never sees the unfiltered table, so lags, rolling statistics and "latest value" are
  all computed AFTER filtering, per origin.
* The target quarter-hours' own actuals are never read (they are NaN in the window anyway).
* Day-ahead forecasts / spot for the target quarter-hours ARE used: they are present in the
  window only if published by the origin.
* aFRR series are sparse by design: absence = no activation. They are summarised as counts
  and means inside a window that ends at the latest usable imbalance quarter-hour (same 60 min
  publication lag as the aFRR rows), never forward-filled.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd

from .availability import DEFAULT_HORIZON, AvailabilityIndex, Window

IMB, SPOT, DIRN = "fi_imbalance_price", "fi_spot_price", "fi_mfrr_direction"
DAY = 96  # quarter-hours per day
HOUR_Q = 4  # quarter-hours per hour (day-ahead schedules are hourly)
SPIKE_MARGIN = 50.0  # EUR/MWh: spread beyond +-50 counts as an exceptional price
MAX_RUN_LEN_Q = 700  # cap on the "quarters since the direction last flipped" feature
DEFAULT_MIN_HISTORY = 192  # quarter-hours of history an origin needs to be used for training

# feature-name prefix -> human readable driver (used for top_drivers)
DRIVER_GROUPS: list[tuple[str, str]] = [
    ("spread_", "imbalance_minus_spot_history"),
    ("imb_t_", "same_time_previous_days_imbalance"),
    ("spreadt_", "same_time_previous_days_imbalance"),
    ("imb_", "latest_imbalance_price"),
    ("dir_", "mfrr_direction_history"),
    ("mfrr_", "mfrr_prices_and_activation"),
    ("afrr_", "afrr_activity"),
    ("spot_", "spot_price"),
    ("cons_fc", "consumption_forecast_da"),
    ("wind_", "wind_forecast_da"),
    ("solar_", "solar_forecast_da"),
    ("resload_", "residual_load_forecast"),
    ("cons_", "consumption_actual"),
    ("prod_", "production_actual"),
    ("flow_", "cross_border_flows"),
    ("nb_", "neighbour_imbalance_prices"),
    ("load_", "neighbour_load_forecasts"),
    ("cap_", "fi_ee_capacity"),
    ("cal_", "calendar"),
    ("step", "forecast_horizon"),
]


# Input groups that the web viewer can switch off (each switch = a separately trained model variant,
# see scripts/run_variants.py). Residual load is built from all three forecasts (consumption - wind - solar),
# so those features go whenever any group is off.
TOGGLE_GROUPS: dict[str, tuple[str, ...]] = {
    "solar": ("solar_",),
    "wind": ("wind_",),
    "consumption": ("cons_fc",),  # day-ahead consumption forecast and its error features (cons_fcerr_*)
}
RESIDUAL_LOAD = ("resload_",)


def dropped_features(columns: Sequence[str], off_groups: Sequence[str]) -> list[str]:
    """Feature names to remove when the given toggle groups are switched off."""
    if not off_groups:
        return []
    prefixes = [prefix for group in off_groups for prefix in TOGGLE_GROUPS[group]] + list(RESIDUAL_LOAD)
    return [name for name in columns if name.startswith(tuple(prefixes))]


def driver_of(feature: str) -> str:
    """Human-readable driver group of a feature (first matching prefix in DRIVER_GROUPS)."""
    for prefix, name in DRIVER_GROUPS:
        if feature.startswith(prefix):
            return name
    return feature


def _last_valid(x: np.ndarray, upto: int) -> tuple[int, float]:
    """(index, value) of the last non-NaN entry in x[:upto]; (-1, nan) if none."""
    idx = np.flatnonzero(~np.isnan(x[:upto]))
    return (int(idx[-1]), float(x[idx[-1]])) if idx.size else (-1, np.nan)


def _take(x: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """x[idx] with NaN for indices outside the window (no negative-index wrap-around)."""
    idx = np.asarray(idx)
    ok = (idx >= 0) & (idx < len(x))
    return np.where(ok, x[np.clip(idx, 0, len(x) - 1)], np.nan)


def _at(x: np.ndarray, i: int) -> float:
    """x[i], or NaN when i is outside the window."""
    return float(x[i]) if 0 <= i < len(x) else np.nan


def _stat(fn: Callable[[np.ndarray], float], x: np.ndarray, end: int, n: int) -> float:
    """fn over x[end-n+1 : end+1] (NaN-ignoring; NaN if the window is empty/all NaN)."""
    if end < 0:
        return np.nan
    seg = x[max(0, end - n + 1) : end + 1]
    if seg.size == 0 or np.isnan(seg).all():
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(fn(seg))


def _share(x: np.ndarray, condition: np.ndarray) -> np.ndarray:
    """0/1 indicator of ``condition`` that stays NaN where ``x`` is NaN (so means ignore missing quarter-hours)."""
    return np.where(np.isnan(x), np.nan, condition.astype(float))


def _imbalance_features(f: dict[str, float], imb: np.ndarray, spot: np.ndarray, origin_row: int) -> tuple[int, float]:
    """Imbalance price history and imbalance-minus-spot spread; returns (anchor index, latest price)."""
    anchor, imb_last = _last_valid(imb, origin_row)
    f["imb_last"] = imb_last
    f["imb_age_q"] = (origin_row - anchor) if anchor >= 0 else np.nan
    for lag in (1, 2, 3, 4, 8, 16, 32, 96):
        f[f"imb_lag{lag}"] = _at(imb, anchor - lag) if anchor >= 0 else np.nan
    for n_q in (4, 16, 96):
        f[f"imb_mean{n_q}"] = _stat(np.nanmean, imb, anchor, n_q)
    f["imb_std16"] = _stat(np.nanstd, imb, anchor, 16)
    f["imb_std96"] = _stat(np.nanstd, imb, anchor, 96)
    f["imb_max16"] = _stat(np.nanmax, imb, anchor, 16)
    f["imb_min16"] = _stat(np.nanmin, imb, anchor, 16)
    f["imb_med96"] = _stat(np.nanmedian, imb, anchor, 96)
    f["imb_diff4"] = imb_last - f["imb_lag4"]

    # spread = imbalance - spot (spot of past quarter-hours is long published)
    spread = imb - spot
    f["spread_last"] = _at(spread, anchor)
    for n_q in (4, 16, 96):
        f[f"spread_mean{n_q}"] = _stat(np.nanmean, spread, anchor, n_q)
    f["spread_std16"] = _stat(np.nanstd, spread, anchor, 16)
    f["spread_abs_mean16"] = _stat(np.nanmean, np.abs(spread), anchor, 16)
    f["spread_share_hi16"] = _stat(np.nanmean, _share(spread, spread > SPIKE_MARGIN), anchor, 16)
    f["spread_share_lo16"] = _stat(np.nanmean, _share(spread, spread < -SPIKE_MARGIN), anchor, 16)
    f["spread_share_hi96"] = _stat(np.nanmean, _share(spread, spread > SPIKE_MARGIN), anchor, 96)
    f["spread_share_lo96"] = _stat(np.nanmean, _share(spread, spread < -SPIKE_MARGIN), anchor, 96)
    return anchor, imb_last


def _mfrr_features(
    f: dict[str, float], col: Callable[[str], np.ndarray], spot: np.ndarray, origin_row: int, imb_anchor: int
) -> None:
    """mFRR direction, prices and activation volumes (latest usable values and short means)."""
    direction = col(DIRN)
    d_anchor, dir_last = _last_valid(direction, origin_row)
    f["dir_last"] = dir_last
    for n_q in (4, 16, 96):
        f[f"dir_up_share{n_q}"] = _stat(np.nanmean, _share(direction, direction == 1), d_anchor, n_q)
        f[f"dir_down_share{n_q}"] = _stat(np.nanmean, _share(direction, direction == -1), d_anchor, n_q)
    f["dir_none_share96"] = _stat(np.nanmean, _share(direction, direction == 0), d_anchor, 96)
    f["dir_mean4"] = _stat(np.nanmean, direction, d_anchor, 4)
    # quarters since the direction last flipped
    if d_anchor >= 0:
        seen = direction[: d_anchor + 1]
        valid = np.flatnonzero(~np.isnan(seen))
        changes = np.flatnonzero(np.diff(seen[valid]) != 0) if valid.size > 1 else np.array([], int)
        f["dir_run_len"] = (
            float(valid[-1] - valid[changes[-1] + 1]) if changes.size else float(min(len(valid), MAX_RUN_LEN_Q))
        )
    else:
        f["dir_run_len"] = np.nan

    for name in ("fi_mfrr_up_price", "fi_mfrr_down_price", "fi_mfrr_up_activated", "fi_mfrr_down_activated"):
        x = col(name)
        x_anchor, x_last = _last_valid(x, origin_row)
        short = name.replace("fi_", "")
        f[f"{short}_last"] = x_last
        f[f"{short}_mean4"] = _stat(np.nanmean, x, x_anchor, 4)
        f[f"{short}_mean16"] = _stat(np.nanmean, x, x_anchor, 16)
    f["mfrr_up_minus_spot"] = f["mfrr_up_price_last"] - _at(spot, imb_anchor)
    f["mfrr_down_minus_spot"] = f["mfrr_down_price_last"] - _at(spot, imb_anchor)
    f["mfrr_act_net_last"] = f["mfrr_up_activated_last"] - f["mfrr_down_activated_last"]
    f["mfrr_act_net_mean16"] = f["mfrr_up_activated_mean16"] - f["mfrr_down_activated_mean16"]


def _afrr_features(f: dict[str, float], col: Callable[[str], np.ndarray], imb_anchor: int) -> None:
    """aFRR (sparse, no row = no activation): counts and means inside a window ending at the anchor."""
    for side in ("up", "down"):
        x = col(f"fi_afrr_{side}_price")
        for n_q in (4, 16, 96):
            seen = x[max(0, imb_anchor - n_q + 1) : imb_anchor + 1] if imb_anchor >= 0 else np.array([])
            f[f"afrr_{side}_cnt{n_q}"] = float((~np.isnan(seen)).sum()) if seen.size else np.nan
        f[f"afrr_{side}_mean16"] = _stat(np.nanmean, x, imb_anchor, 16)
        f[f"afrr_{side}_mean96"] = _stat(np.nanmean, x, imb_anchor, 96)
    f["afrr_net_cnt16"] = f["afrr_up_cnt16"] - f["afrr_down_cnt16"]


def _consumption_flow_features(f: dict[str, float], col: Callable[[str], np.ndarray], origin_row: int) -> float:
    """Consumption, production and cross-border flows (about 30 min publication lag); returns last consumption."""
    cons, prod, cons_fc = col("fi_consumption"), col("fi_production"), col("fi_consumption_fc_da")
    c_anchor, cons_last = _last_valid(cons, origin_row)
    p_anchor, prod_last = _last_valid(prod, origin_row)
    f["cons_last"], f["prod_last"] = cons_last, prod_last
    f["cons_diff4"] = cons_last - _at(cons, c_anchor - 4) if c_anchor >= 0 else np.nan
    f["prod_diff4"] = prod_last - _at(prod, p_anchor - 4) if p_anchor >= 0 else np.nan
    f["cons_mean16"] = _stat(np.nanmean, cons, c_anchor, 16)
    f["prod_mean16"] = _stat(np.nanmean, prod, p_anchor, 16)
    cons_err = cons - cons_fc  # realised minus day-ahead forecast (past only)
    f["cons_fcerr_last"] = _at(cons_err, c_anchor)
    f["cons_fcerr_mean4"] = _stat(np.nanmean, cons_err, c_anchor, 4)
    f["cons_fcerr_mean16"] = _stat(np.nanmean, cons_err, c_anchor, 16)
    f["prod_minus_cons_last"] = prod_last - cons_last
    both_anchor = min(c_anchor, p_anchor)
    f["prod_minus_cons_mean4"] = _stat(np.nanmean, prod - cons, both_anchor, 4) if both_anchor >= 0 else np.nan
    flows = []
    for neighbour in ("se3", "no4", "se1", "ee"):
        x = col(f"fi_{neighbour}_flow")
        x_anchor, x_last = _last_valid(x, origin_row)
        f[f"flow_{neighbour}_last"] = x_last
        f[f"flow_{neighbour}_diff4"] = x_last - _at(x, x_anchor - 4) if x_anchor >= 0 else np.nan
        flows.append(x)
    flow_stack = np.vstack(flows)
    net = np.where(np.all(np.isnan(flow_stack), axis=0), np.nan, np.nansum(flow_stack, axis=0))
    n_anchor, net_last = _last_valid(net, origin_row)
    f["flow_net_last"] = net_last
    f["flow_net_mean16"] = _stat(np.nanmean, net, n_anchor, 16)
    f["flow_net_diff4"] = net_last - _at(net, n_anchor - 4) if n_anchor >= 0 else np.nan
    return cons_last


def _neighbour_features(
    f: dict[str, float], col: Callable[[str], np.ndarray], imb: np.ndarray, origin_row: int
) -> None:
    """Neighbouring areas' imbalance prices and load forecasts (about 120 min publication lag)."""
    for area in ("se1", "se3", "ee"):
        for kind in ("long", "short"):
            x = col(f"{area}_imbalance_price_{kind}")
            x_anchor, x_last = _last_valid(x, origin_row)
            f[f"nb_{area}_{kind}_last"] = x_last
            if kind == "long":
                f[f"nb_{area}_mean16"] = _stat(np.nanmean, x, x_anchor, 16)
                f[f"nb_{area}_minus_fi"] = x_last - _at(imb, x_anchor)  # compare at the SAME quarter-hour
    f["nb_se3_spread_last"] = f["nb_se3_short_last"] - f["nb_se3_long_last"]
    for area in ("se1", "se3", "ee"):
        x = col(f"{area}_load_fc_da")
        x_anchor, x_last = _last_valid(x, origin_row)
        f[f"load_{area}_last"] = x_last
        f[f"load_{area}_diff4"] = x_last - _at(x, x_anchor - 4) if x_anchor >= 0 else np.nan


def _day_ahead_features(
    f: dict[str, float], col: Callable[[str], np.ndarray], spot: np.ndarray, origin_row: int, horizon: int
) -> None:
    """Day-ahead block known at the origin, summarised over the whole forecast horizon."""
    wind, solar, cons_fc = col("fi_wind_fc_da"), col("fi_solar_fc_da"), col("fi_consumption_fc_da")
    last = origin_row + horizon - 1  # last target row
    f["spot_now"] = _at(spot, origin_row)
    f["spot_hmean"] = _stat(np.nanmean, spot, last, horizon)
    f["spot_hmax"] = _stat(np.nanmax, spot, last, horizon)
    f["spot_hmin"] = _stat(np.nanmin, spot, last, horizon)
    f["spot_past_mean96"] = _stat(np.nanmean, spot, origin_row - 1, 96)
    f["wind_hmean"] = _stat(np.nanmean, wind, last, horizon)
    f["wind_hmean_chg1d"] = f["wind_hmean"] - _stat(np.nanmean, wind, last - DAY, horizon)
    f["solar_hmean"] = _stat(np.nanmean, solar, last, horizon)
    f["cons_fc_hmean"] = _stat(np.nanmean, cons_fc, last, horizon)
    f["cons_fc_hmean_chg1d"] = f["cons_fc_hmean"] - _stat(np.nanmean, cons_fc, last - DAY, horizon)
    resid_load = cons_fc - wind - solar
    f["resload_hmean"] = _stat(np.nanmean, resid_load, last, horizon)
    f["resload_hmean_chg1d"] = f["resload_hmean"] - _stat(np.nanmean, resid_load, last - DAY, horizon)
    f["cap_fi_ee_hmin"] = _stat(np.nanmin, col("fi_ee_capacity_da"), last, horizon)


def _step_features(
    w: Window,
    f: dict[str, float],
    spot: np.ndarray,
    imb: np.ndarray,
    cons_last: float,
    horizon: int,
) -> pd.DataFrame:
    """Repeat the origin-level features per step and add the per-target-quarter-hour features."""
    col = w.col
    origin_row = w.origin_row
    target_rows = origin_row + np.arange(horizon)  # step 1 starts at the origin
    n_rows = len(w.values)
    imb_last = f["imb_last"]
    wind, solar, cons_fc = col("fi_wind_fc_da"), col("fi_solar_fc_da"), col("fi_consumption_fc_da")
    cap_fi_ee, cap_ee_fi = col("fi_ee_capacity_da"), col("ee_fi_capacity_da")
    resid_load = cons_fc - wind - solar

    base = pd.DataFrame({k: np.full(horizon, v) for k, v in f.items()})
    base["step"] = np.arange(1, horizon + 1)
    ts = w.index[target_rows]
    base["cal_hod_utc"] = np.asarray(ts.hour + ts.minute / 60.0, dtype=float)
    base["cal_hour_local"] = col("cal_hour_local")[target_rows]
    base["cal_weekday_local"] = col("cal_weekday_local")[target_rows]
    base["cal_is_holiday_fi"] = col("cal_is_holiday_fi")[target_rows]
    base["cal_is_dst"] = col("cal_is_dst")[target_rows]
    spot_t = spot[target_rows]
    base["spot_t"] = spot_t
    base["spot_t_minus_imb_last"] = spot_t - imb_last
    base["spot_t_minus_now"] = spot_t - f["spot_now"]
    base["spot_t_minus_hmean"] = spot_t - f["spot_hmean"]
    base["spot_t_chg1d"] = spot_t - _take(spot, target_rows - DAY)
    base["spot_t_minus_past_mean96"] = spot_t - f["spot_past_mean96"]
    wind_t, solar_t, cons_fc_t = wind[target_rows], solar[target_rows], cons_fc[target_rows]
    base["wind_t"], base["solar_t"], base["cons_fc_t"] = wind_t, solar_t, cons_fc_t
    base["resload_t"] = cons_fc_t - wind_t - solar_t
    base["wind_t_chg1d"] = wind_t - _take(wind, target_rows - DAY)
    base["solar_t_chg1d"] = solar_t - _take(solar, target_rows - DAY)
    base["cons_fc_t_chg1d"] = cons_fc_t - _take(cons_fc, target_rows - DAY)
    base["resload_t_chg1d"] = base["resload_t"] - _take(resid_load, target_rows - DAY)
    base["wind_t_minus_now"] = wind_t - wind[origin_row]
    base["cons_fc_t_minus_last"] = cons_fc_t - cons_last
    base["cap_fi_ee_t"] = cap_fi_ee[target_rows]
    base["cap_ee_fi_t"] = cap_ee_fi[target_rows]
    # same quarter-hour one and seven days earlier (known: far in the past)
    for lag_name, lag in (("1d", DAY), ("7d", 7 * DAY)):
        idx = target_rows - lag
        in_window = idx >= 0
        imb_lag = np.where(in_window, imb[np.clip(idx, 0, n_rows - 1)], np.nan)
        spot_lag = np.where(in_window, spot[np.clip(idx, 0, n_rows - 1)], np.nan)
        base[f"imb_t_{lag_name}"] = imb_lag
        base[f"spreadt_{lag_name}"] = imb_lag - spot_lag
    base["imb_last_minus_spot_t"] = imb_last - spot_t
    # hour-boundary ramps (day-ahead schedules are hourly, imbalances concentrate at hour changes)
    base["cal_qh"] = np.asarray(ts.minute // 15, dtype=float)
    base["spot_ramp_back"] = spot_t - _take(spot, target_rows - HOUR_Q)
    base["spot_ramp_fwd"] = _take(spot, target_rows + HOUR_Q) - spot_t
    base["resload_ramp_back"] = base["resload_t"] - _take(resid_load, target_rows - HOUR_Q)
    base["resload_ramp_fwd"] = _take(resid_load, target_rows + HOUR_Q) - base["resload_t"]
    base["cons_fc_ramp_back"] = cons_fc_t - _take(cons_fc, target_rows - HOUR_Q)
    base["wind_ramp_back"] = wind_t - _take(wind, target_rows - HOUR_Q)
    base["solar_ramp_back"] = solar_t - _take(solar, target_rows - HOUR_Q)
    base["mfrr_up_last_minus_spot_t"] = f["mfrr_up_price_last"] - spot_t
    base["mfrr_down_last_minus_spot_t"] = f["mfrr_down_price_last"] - spot_t
    return base


def build_origin_features(w: Window, horizon: int = DEFAULT_HORIZON) -> pd.DataFrame:
    """Return a ``horizon``-row frame (one row per step) of features known at ``w.origin``.

    ``w`` is already availability-filtered, so every lag/rolling/latest value below is computed after filtering.
    The order in which keys are added to ``f`` fixes the feature column order, so keep it stable.
    """
    origin_row = w.origin_row
    if origin_row + horizon - 1 >= len(w.values):
        raise ValueError("window does not cover the horizon")
    col = w.col
    imb, spot = col(IMB), col(SPOT)
    f: dict[str, float] = {}
    imb_anchor, _ = _imbalance_features(f, imb, spot, origin_row)
    _mfrr_features(f, col, spot, origin_row, imb_anchor)
    _afrr_features(f, col, imb_anchor)
    cons_last = _consumption_flow_features(f, col, origin_row)
    _neighbour_features(f, col, imb, origin_row)
    _day_ahead_features(f, col, spot, origin_row, horizon)
    return _step_features(w, f, spot, imb, cons_last, horizon)


def data_cutoff(w: Window) -> pd.Timestamp:
    """Latest first_usable_origin_utc among the cells present in the window (<= origin)."""
    return pd.Timestamp(int(w.first_usable.max()), tz="UTC")


def build_dataset(
    index: AvailabilityIndex,
    origins: Sequence[pd.Timestamp] | pd.DatetimeIndex,
    cfg: dict,
    label_cutoff: pd.Timestamp | str | None = None,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> pd.DataFrame:
    """Features (and, if ``label_cutoff`` is given, labels) for many origins.

    label_cutoff: labels are read only if usable at this origin (end of the training window).
    Origins whose 40 imbalance labels are not all known by then are dropped (training only).
    """
    horizon, lookback = cfg["horizon_steps"], cfg["lookback_quarters"]
    frames = []
    for origin_like in origins:
        origin = pd.Timestamp(origin_like)
        origin_row = index.row_of(origin)
        if label_cutoff is not None and origin_row < min_history:
            continue
        w = index.at(origin, lookback, horizon)
        X = build_origin_features(w, horizon)
        X.insert(0, "forecast_origin_utc", origin)
        delivery = pd.DatetimeIndex(w.index[w.origin_row : w.origin_row + horizon])
        X.insert(1, "delivery_start_utc", delivery)
        X.insert(2, "data_cutoff_utc", data_cutoff(w))
        if label_cutoff is not None:
            y = index.labels(delivery, IMB, label_cutoff)
            if np.isnan(y).any():
                continue
            X["y"] = y
            X["dir"] = index.labels(delivery, DIRN, label_cutoff)
            X["spot_label"] = index.labels(delivery, SPOT, label_cutoff)
        frames.append(X)
    return pd.concat(frames, ignore_index=True)


FEATURE_EXCLUDE = {"forecast_origin_utc", "delivery_start_utc", "data_cutoff_utc", "y", "dir", "spot_label"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Model input columns: everything except identifiers and labels."""
    return [name for name in df.columns if name not in FEATURE_EXCLUDE]
