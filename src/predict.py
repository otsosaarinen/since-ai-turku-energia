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

COLS = ["forecast_origin_utc", "delivery_start_utc", "step", "p10", "p50", "p90", "p_up", "p_down", "p_none",
        "p_spike_high", "p_spike_low", "data_cutoff_utc", "top_drivers"]


def top_drivers(contrib: np.ndarray, feats: list[str], k: int = 3) -> list[str]:
    """Per row: top-k driver groups by |SHAP contribution| (contrib has a trailing bias column)."""
    groups = sorted({driver_of(f) for f in feats})
    gi = {g: i for i, g in enumerate(groups)}
    M = np.zeros((len(feats), len(groups)))
    for j, f in enumerate(feats):
        M[j, gi[driver_of(f)]] = 1.0
    G = np.abs(contrib[:, :-1]) @ M
    order = np.argsort(-G, axis=1)[:, :k]
    return [";".join(groups[i] for i in row) for row in order]


def predict_frame(mdl: Models, X: pd.DataFrame, with_drivers: bool = True) -> pd.DataFrame:
    feats = mdl.features
    Xf = X[feats]
    cfg = mdl.cfg
    base = X["spot_t"].to_numpy() if cfg["model"]["target"] == "spread" else np.zeros(len(X))
    if np.isnan(base).any():  # spot of the target not published: fall back to the latest imbalance price
        base = np.where(np.isnan(base), X["imb_last"].to_numpy(), base)
    avg = lambda k: np.mean([b.predict(Xf) for b in mdl.boosters[k]], axis=0)  # noqa: E731
    q = np.column_stack([avg("p10") + mdl.offsets["p10"], avg("p50"), avg("p90") + mdl.offsets["p90"]]) + base[:, None]
    q = np.sort(q, axis=1)
    pd_ = avg("dir")                                    # columns: down, none, up
    pd_ = np.clip(pd_, 1e-4, 1.0)
    pd_ = pd_ / pd_.sum(axis=1, keepdims=True)
    hi = np.clip(avg("hi"), 0, 1)
    lo = np.clip(avg("lo"), 0, 1)
    s = hi + lo
    scale = np.where(s > 1, 1 / np.maximum(s, 1e-12), 1.0)
    out = pd.DataFrame({
        "forecast_origin_utc": X["forecast_origin_utc"].to_numpy(),
        "delivery_start_utc": X["delivery_start_utc"].to_numpy(),
        "step": X["step"].to_numpy().astype(int),
        "p10": q[:, 0], "p50": q[:, 1], "p90": q[:, 2],
        "p_up": pd_[:, 2], "p_down": pd_[:, 0], "p_none": pd_[:, 1],
        "p_spike_high": hi * scale, "p_spike_low": lo * scale,
        "data_cutoff_utc": X["data_cutoff_utc"].to_numpy(),
    })
    if with_drivers:
        contrib = np.mean([b.predict(Xf, pred_contrib=True) for b in mdl.boosters["p50"]], axis=0)
        out["top_drivers"] = top_drivers(contrib, feats)
    else:
        out["top_drivers"] = ""
    return out[COLS]


def predict_origins(mdl: Models, index: AvailabilityIndex, origins, with_drivers: bool = True) -> pd.DataFrame:
    X = build_dataset(index, origins, mdl.cfg, label_cutoff=None)
    return predict_frame(mdl, X, with_drivers)
