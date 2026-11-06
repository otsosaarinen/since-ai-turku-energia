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

import numpy as np
import pandas as pd

from .availability import AvailabilityIndex, Window

IMB, SPOT, DIRN = "fi_imbalance_price", "fi_spot_price", "fi_mfrr_direction"
DAY = 96  # quarter-hours per day

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


def driver_of(feature: str) -> str:
    for prefix, name in DRIVER_GROUPS:
        if feature.startswith(prefix):
            return name
    return feature


def _last_valid(x: np.ndarray, upto: int):
    """(index, value) of the last non-NaN entry in x[:upto]; (-1, nan) if none."""
    idx = np.flatnonzero(~np.isnan(x[:upto]))
    return (int(idx[-1]), float(x[idx[-1]])) if idx.size else (-1, np.nan)


def _take(x: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """x[idx] with NaN for indices outside the window (no negative-index wrap-around)."""
    idx = np.asarray(idx)
    ok = (idx >= 0) & (idx < len(x))
    return np.where(ok, x[np.clip(idx, 0, len(x) - 1)], np.nan)


def _at(x: np.ndarray, i: int) -> float:
    return float(x[i]) if 0 <= i < len(x) else np.nan


def _stat(fn, x: np.ndarray, end: int, n: int) -> float:
    """fn over x[end-n+1 : end+1] (NaN-ignoring; NaN if the window is empty/all NaN)."""
    if end < 0:
        return np.nan
    seg = x[max(0, end - n + 1): end + 1]
    if seg.size == 0 or np.isnan(seg).all():
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(fn(seg))


def build_origin_features(w: Window, horizon: int = 40) -> pd.DataFrame:
    """Return a ``horizon``-row frame (one row per step) of features known at ``w.origin``."""
    o = w.origin_row
    n = len(w.values)
    tr = o + np.arange(horizon)                      # target rows (step 1 starts at the origin)
    assert tr[-1] < n, "window does not cover the horizon"
    c = w.col
    imb, spot = c(IMB), c(SPOT)
    f: dict[str, float] = {}

    # ---------------- imbalance price history (anchor = latest usable quarter-hour) ----------
    a, imb_last = _last_valid(imb, o)
    f["imb_last"] = imb_last
    f["imb_age_q"] = (o - a) if a >= 0 else np.nan
    for j in (1, 2, 3, 4, 8, 16, 32, 96):
        f[f"imb_lag{j}"] = _at(imb, a - j) if a >= 0 else np.nan
    for n_ in (4, 16, 96):
        f[f"imb_mean{n_}"] = _stat(np.nanmean, imb, a, n_)
    f["imb_std16"] = _stat(np.nanstd, imb, a, 16)
    f["imb_std96"] = _stat(np.nanstd, imb, a, 96)
    f["imb_max16"] = _stat(np.nanmax, imb, a, 16)
    f["imb_min16"] = _stat(np.nanmin, imb, a, 16)
    f["imb_med96"] = _stat(np.nanmedian, imb, a, 96)
    f["imb_diff4"] = imb_last - f["imb_lag4"]

    # spread = imbalance - spot (spot of past quarter-hours is long published)
    spread = imb - spot
    f["spread_last"] = _at(spread, a)
    for n_ in (4, 16, 96):
        f[f"spread_mean{n_}"] = _stat(np.nanmean, spread, a, n_)
    f["spread_std16"] = _stat(np.nanstd, spread, a, 16)
    f["spread_abs_mean16"] = _stat(np.nanmean, np.abs(spread), a, 16)
    f["spread_share_hi16"] = _stat(np.nanmean, np.where(np.isnan(spread), np.nan, (spread > 50).astype(float)), a, 16)
    f["spread_share_lo16"] = _stat(np.nanmean, np.where(np.isnan(spread), np.nan, (spread < -50).astype(float)), a, 16)
    f["spread_share_hi96"] = _stat(np.nanmean, np.where(np.isnan(spread), np.nan, (spread > 50).astype(float)), a, 96)
    f["spread_share_lo96"] = _stat(np.nanmean, np.where(np.isnan(spread), np.nan, (spread < -50).astype(float)), a, 96)

    # ---------------- mFRR direction / prices / activations ----------------------------------
    d = c(DIRN)
    da, dlast = _last_valid(d, o)
    f["dir_last"] = dlast
    for n_ in (4, 16, 96):
        f[f"dir_up_share{n_}"] = _stat(np.nanmean, np.where(np.isnan(d), np.nan, (d == 1).astype(float)), da, n_)
        f[f"dir_down_share{n_}"] = _stat(np.nanmean, np.where(np.isnan(d), np.nan, (d == -1).astype(float)), da, n_)
    f["dir_none_share96"] = _stat(np.nanmean, np.where(np.isnan(d), np.nan, (d == 0).astype(float)), da, 96)
    f["dir_mean4"] = _stat(np.nanmean, d, da, 4)
    # quarters since the direction last flipped
    if da >= 0:
        seg = d[: da + 1]
        valid = np.flatnonzero(~np.isnan(seg))
        changes = np.flatnonzero(np.diff(seg[valid]) != 0) if valid.size > 1 else np.array([], int)
        f["dir_run_len"] = float(valid[-1] - valid[changes[-1] + 1]) if changes.size else float(min(len(valid), 700))
    else:
        f["dir_run_len"] = np.nan

    for name in ("fi_mfrr_up_price", "fi_mfrr_down_price", "fi_mfrr_up_activated", "fi_mfrr_down_activated"):
        x = c(name)
        xa, xv = _last_valid(x, o)
        short = name.replace("fi_", "")
        f[f"{short}_last"] = xv
        f[f"{short}_mean4"] = _stat(np.nanmean, x, xa, 4)
        f[f"{short}_mean16"] = _stat(np.nanmean, x, xa, 16)
    f["mfrr_up_minus_spot"] = f["mfrr_up_price_last"] - _at(spot, a)
    f["mfrr_down_minus_spot"] = f["mfrr_down_price_last"] - _at(spot, a)
    f["mfrr_act_net_last"] = f["mfrr_up_activated_last"] - f["mfrr_down_activated_last"]
    f["mfrr_act_net_mean16"] = f["mfrr_up_activated_mean16"] - f["mfrr_down_activated_mean16"]

    # ---------------- aFRR (sparse): counts / means inside a window ending at the anchor -----
    for side in ("up", "down"):
        x = c(f"fi_afrr_{side}_price")
        for n_ in (4, 16, 96):
            seg = x[max(0, a - n_ + 1): a + 1] if a >= 0 else np.array([])
            f[f"afrr_{side}_cnt{n_}"] = float((~np.isnan(seg)).sum()) if seg.size else np.nan
        f[f"afrr_{side}_mean16"] = _stat(np.nanmean, x, a, 16)
        f[f"afrr_{side}_mean96"] = _stat(np.nanmean, x, a, 96)
    f["afrr_net_cnt16"] = f["afrr_up_cnt16"] - f["afrr_down_cnt16"]

    # ---------------- consumption / production / flows (30 min lag) ---------------------------
    cons, prod, cons_fc = c("fi_consumption"), c("fi_production"), c("fi_consumption_fc_da")
    ca, cv = _last_valid(cons, o)
    pa, pv = _last_valid(prod, o)
    f["cons_last"], f["prod_last"] = cv, pv
    f["cons_diff4"] = cv - _at(cons, ca - 4) if ca >= 0 else np.nan
    f["prod_diff4"] = pv - _at(prod, pa - 4) if pa >= 0 else np.nan
    f["cons_mean16"] = _stat(np.nanmean, cons, ca, 16)
    f["prod_mean16"] = _stat(np.nanmean, prod, pa, 16)
    cons_err = cons - cons_fc                         # realised minus day-ahead forecast (past only)
    f["cons_fcerr_last"] = _at(cons_err, ca)
    f["cons_fcerr_mean4"] = _stat(np.nanmean, cons_err, ca, 4)
    f["cons_fcerr_mean16"] = _stat(np.nanmean, cons_err, ca, 16)
    f["prod_minus_cons_last"] = pv - cv
    f["prod_minus_cons_mean4"] = _stat(np.nanmean, prod - cons, min(ca, pa), 4) if min(ca, pa) >= 0 else np.nan
    flows = {}
    for k in ("se3", "no4", "se1", "ee"):
        x = c(f"fi_{k}_flow")
        xa, xv = _last_valid(x, o)
        f[f"flow_{k}_last"] = xv
        f[f"flow_{k}_diff4"] = xv - _at(x, xa - 4) if xa >= 0 else np.nan
        flows[k] = x
    net = np.nansum(np.vstack(list(flows.values())), axis=0)
    all_nan = np.all(np.isnan(np.vstack(list(flows.values()))), axis=0)
    net = np.where(all_nan, np.nan, net)
    na_, nv = _last_valid(net, o)
    f["flow_net_last"] = nv
    f["flow_net_mean16"] = _stat(np.nanmean, net, na_, 16)
    f["flow_net_diff4"] = nv - _at(net, na_ - 4) if na_ >= 0 else np.nan

    # ---------------- neighbour imbalance prices & loads (120 min lag) ------------------------
    for k in ("se1", "se3", "ee"):
        for kind in ("long", "short"):
            x = c(f"{k}_imbalance_price_{kind}")
            xa, xv = _last_valid(x, o)
            f[f"nb_{k}_{kind}_last"] = xv
            if kind == "long":
                f[f"nb_{k}_mean16"] = _stat(np.nanmean, x, xa, 16)
                f[f"nb_{k}_minus_fi"] = xv - _at(imb, xa)    # compare at the SAME quarter-hour
    f["nb_se3_spread_last"] = f["nb_se3_short_last"] - f["nb_se3_long_last"]
    for k in ("se1", "se3", "ee"):
        x = c(f"{k}_load_fc_da")
        xa, xv = _last_valid(x, o)
        f[f"load_{k}_last"] = xv
        f[f"load_{k}_diff4"] = xv - _at(x, xa - 4) if xa >= 0 else np.nan

    # ---------------- day-ahead block known at the origin (origin level) ----------------------
    wind, solar = c("fi_wind_fc_da"), c("fi_solar_fc_da")
    cap1, cap2 = c("fi_ee_capacity_da"), c("ee_fi_capacity_da")
    h = slice(o, o + horizon)
    f["spot_now"] = _at(spot, o)
    f["spot_hmean"] = _stat(np.nanmean, spot, o + horizon - 1, horizon)
    f["spot_hmax"] = _stat(np.nanmax, spot, o + horizon - 1, horizon)
    f["spot_hmin"] = _stat(np.nanmin, spot, o + horizon - 1, horizon)
    f["spot_past_mean96"] = _stat(np.nanmean, spot, o - 1, 96)
    f["wind_hmean"] = _stat(np.nanmean, wind, o + horizon - 1, horizon)
    f["wind_hmean_chg1d"] = f["wind_hmean"] - _stat(np.nanmean, wind, o + horizon - 1 - DAY, horizon)
    f["solar_hmean"] = _stat(np.nanmean, solar, o + horizon - 1, horizon)
    f["cons_fc_hmean"] = _stat(np.nanmean, cons_fc, o + horizon - 1, horizon)
    f["cons_fc_hmean_chg1d"] = f["cons_fc_hmean"] - _stat(np.nanmean, cons_fc, o + horizon - 1 - DAY, horizon)
    resl = cons_fc - wind - solar
    f["resload_hmean"] = _stat(np.nanmean, resl, o + horizon - 1, horizon)
    f["resload_hmean_chg1d"] = f["resload_hmean"] - _stat(np.nanmean, resl, o + horizon - 1 - DAY, horizon)
    f["cap_fi_ee_hmin"] = _stat(np.nanmin, cap1, o + horizon - 1, horizon)

    # ---------------- step-level (target quarter-hour) features -------------------------------
    base = pd.DataFrame({k: np.full(horizon, v) for k, v in f.items()})
    base["step"] = np.arange(1, horizon + 1)
    ts = w.index[tr]
    hod = ts.hour + ts.minute / 60.0
    base["cal_hod_utc"] = np.asarray(hod, dtype=float)
    base["cal_hour_local"] = c("cal_hour_local")[tr]
    base["cal_weekday_local"] = c("cal_weekday_local")[tr]
    base["cal_is_holiday_fi"] = c("cal_is_holiday_fi")[tr]
    base["cal_is_dst"] = c("cal_is_dst")[tr]
    s_t = spot[tr]
    base["spot_t"] = s_t
    base["spot_t_minus_imb_last"] = s_t - imb_last
    base["spot_t_minus_now"] = s_t - f["spot_now"]
    base["spot_t_minus_hmean"] = s_t - f["spot_hmean"]
    base["spot_t_chg1d"] = s_t - _take(spot, tr - DAY)
    base["spot_t_minus_past_mean96"] = s_t - f["spot_past_mean96"]
    ws, sl, cf = wind[tr], solar[tr], cons_fc[tr]
    base["wind_t"], base["solar_t"], base["cons_fc_t"] = ws, sl, cf
    base["resload_t"] = cf - ws - sl
    base["wind_t_chg1d"] = ws - _take(wind, tr - DAY)
    base["solar_t_chg1d"] = sl - _take(solar, tr - DAY)
    base["cons_fc_t_chg1d"] = cf - _take(cons_fc, tr - DAY)
    base["resload_t_chg1d"] = base["resload_t"] - _take(resl, tr - DAY)
    base["wind_t_minus_now"] = ws - wind[o]
    base["cons_fc_t_minus_last"] = cf - cv
    base["cap_fi_ee_t"] = cap1[tr]
    base["cap_ee_fi_t"] = cap2[tr]
    # same quarter-hour one and seven days earlier (known: far in the past)
    for lag_name, lag in (("1d", DAY), ("7d", 7 * DAY)):
        idx = tr - lag
        ok = idx >= 0
        i_lag = np.where(ok, imb[np.clip(idx, 0, n - 1)], np.nan)
        s_lag = np.where(ok, spot[np.clip(idx, 0, n - 1)], np.nan)
        base[f"imb_t_{lag_name}"] = i_lag
        base[f"spreadt_{lag_name}"] = i_lag - s_lag
    base["imb_last_minus_spot_t"] = imb_last - s_t
    # hour-boundary ramps (day-ahead schedules are hourly, imbalances concentrate at hour changes)
    base["cal_qh"] = np.asarray(ts.minute // 15, dtype=float)
    base["spot_ramp_back"] = s_t - _take(spot, tr - 4)
    base["spot_ramp_fwd"] = _take(spot, tr + 4) - s_t
    base["resload_ramp_back"] = base["resload_t"] - _take(resl, tr - 4)
    base["resload_ramp_fwd"] = _take(resl, tr + 4) - base["resload_t"]
    base["cons_fc_ramp_back"] = cf - _take(cons_fc, tr - 4)
    base["wind_ramp_back"] = ws - _take(wind, tr - 4)
    base["solar_ramp_back"] = sl - _take(solar, tr - 4)
    base["mfrr_up_last_minus_spot_t"] = f["mfrr_up_price_last"] - s_t
    base["mfrr_down_last_minus_spot_t"] = f["mfrr_down_price_last"] - s_t
    return base


def data_cutoff(w: Window) -> pd.Timestamp:
    """Latest first_usable_origin_utc among the cells present in the window (<= origin)."""
    return pd.Timestamp(int(w.first_usable.max()), tz="UTC")


def build_dataset(index: AvailabilityIndex, origins, cfg, label_cutoff=None, min_history: int = 192):
    """Features (and, if ``label_cutoff`` is given, labels) for many origins.

    label_cutoff: labels are read only if usable at this origin (end of the training window).
    Origins whose 40 imbalance labels are not all known by then are dropped (training only).
    """
    horizon, lookback = cfg["horizon_steps"], cfg["lookback_quarters"]
    frames = []
    for o in origins:
        o = pd.Timestamp(o)
        ro = index.row_of(o)
        if label_cutoff is not None and ro < min_history:
            continue
        w = index.at(o, lookback, horizon)
        X = build_origin_features(w, horizon)
        X.insert(0, "forecast_origin_utc", o)
        ts = pd.DatetimeIndex(w.index[w.origin_row: w.origin_row + horizon])
        X.insert(1, "delivery_start_utc", ts)
        X.insert(2, "data_cutoff_utc", data_cutoff(w))
        if label_cutoff is not None:
            y = index.labels(ts, IMB, label_cutoff)
            if np.isnan(y).any():
                continue
            X["y"] = y
            X["dir"] = index.labels(ts, DIRN, label_cutoff)
            X["spot_label"] = index.labels(ts, SPOT, label_cutoff)
        frames.append(X)
    return pd.concat(frames, ignore_index=True)


FEATURE_EXCLUDE = {"forecast_origin_utc", "delivery_start_utc", "data_cutoff_utc", "y", "dir", "spot_label"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in FEATURE_EXCLUDE]
