"""Prediction + post-processing for a list of forecast origins.

For every origin the features are rebuilt from the availability-filtered window only.
Post-processing: quantiles are sorted (p10<=p50<=p90), direction probabilities are
renormalised, spike probabilities are clipped so that high+low <= 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .availability import AvailabilityIndex
from .features import build_dataset, driver_of
from .train import Models

DIR_PROB_FLOOR = 1e-4  # keeps every direction probability strictly positive before renormalising
TOP_DRIVER_COUNT = 3
COLS = [
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
    "data_cutoff_utc",
    "top_drivers",
]


def top_drivers(contrib: np.ndarray, feats: list[str], k: int = TOP_DRIVER_COUNT) -> list[str]:
    """Per row: top-k driver groups by |SHAP contribution| (contrib has a trailing bias column)."""
    groups = sorted({driver_of(f) for f in feats})
    group_index = {g: i for i, g in enumerate(groups)}
    membership = np.zeros((len(feats), len(groups)))  # feature -> its driver group (one-hot rows)
    for j, feature in enumerate(feats):
        membership[j, group_index[driver_of(feature)]] = 1.0
    group_strength = np.abs(contrib[:, :-1]) @ membership
    order = np.argsort(-group_strength, axis=1)[:, :k]
    return [";".join(groups[i] for i in row) for row in order]


def predict_frame(mdl: Models, X: pd.DataFrame, with_drivers: bool = True) -> pd.DataFrame:
    """Turn a feature frame into the submission columns (quantiles, probabilities, top drivers)."""
    feats = mdl.features
    Xf = X[feats]
    cfg = mdl.cfg
    base = X["spot_t"].to_numpy() if cfg["model"]["target"] == "spread" else np.zeros(len(X))
    if np.isnan(base).any():  # spot of the target not published: fall back to the latest imbalance price
        base = np.where(np.isnan(base), X["imb_last"].to_numpy(), base)

    def seed_average(key: str) -> np.ndarray:
        return np.mean([booster.predict(Xf) for booster in mdl.boosters[key]], axis=0)

    quantiles = (
        np.column_stack(
            [seed_average("p10") + mdl.offsets["p10"], seed_average("p50"), seed_average("p90") + mdl.offsets["p90"]]
        )
        + base[:, None]
    )
    quantiles = np.sort(quantiles, axis=1)  # no quantile crossing
    dir_prob = seed_average("dir")  # columns: down, none, up
    dir_prob = np.clip(dir_prob, DIR_PROB_FLOOR, 1.0)
    dir_prob = dir_prob / dir_prob.sum(axis=1, keepdims=True)
    hi = np.clip(seed_average("hi"), 0, 1)
    lo = np.clip(seed_average("lo"), 0, 1)
    total = hi + lo
    scale = np.where(total > 1, 1 / np.maximum(total, 1e-12), 1.0)
    out = pd.DataFrame(
        {
            "forecast_origin_utc": X["forecast_origin_utc"].to_numpy(),
            "delivery_start_utc": X["delivery_start_utc"].to_numpy(),
            "step": X["step"].to_numpy().astype(int),
            "p10": quantiles[:, 0],
            "p50": quantiles[:, 1],
            "p90": quantiles[:, 2],
            "p_up": dir_prob[:, 2],
            "p_down": dir_prob[:, 0],
            "p_none": dir_prob[:, 1],
            "p_spike_high": hi * scale,
            "p_spike_low": lo * scale,
            "data_cutoff_utc": X["data_cutoff_utc"].to_numpy(),
        }
    )
    if with_drivers:
        contrib = np.mean([booster.predict(Xf, pred_contrib=True) for booster in mdl.boosters["p50"]], axis=0)
        out["top_drivers"] = top_drivers(contrib, feats)
    else:
        out["top_drivers"] = ""
    return out[COLS]


def predict_origins(
    mdl: Models, index: AvailabilityIndex, origins: pd.DatetimeIndex, with_drivers: bool = True
) -> pd.DataFrame:
    """Build features for each origin from the availability-filtered window and predict all 40 steps."""
    X = build_dataset(index, origins, mdl.cfg, label_cutoff=None)
    return predict_frame(mdl, X, with_drivers)
