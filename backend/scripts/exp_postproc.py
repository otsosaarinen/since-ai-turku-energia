"""Post-processing experiments on the 8 rolling windows (one model fit per window, variants applied afterwards).

A: direction 'none' probability fixed to the training share. B: spike probabilities shifted in logit space by
(recent 14-day base rate - overall training base rate), with strength s in {0.5, 1}.

usage: uv run scripts/exp_postproc.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import run_rolling as rr  # sibling script; Python puts the script's folder on the import path

from src import predict, train

PROB_EPS = 1e-4  # keeps logit finite for probabilities of exactly 0 or 1
RECENT_BASE_RATE_DAYS = 14
SHIFT_STRENGTHS = (0.5, 1.0)


def logit(x: np.ndarray | float) -> np.ndarray | float:
    """Log-odds of a probability, clipped away from 0 and 1."""
    x = np.clip(x, PROB_EPS, 1 - PROB_EPS)
    return np.log(x / (1 - x))


def sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    """Inverse of logit."""
    return 1 / (1 + np.exp(-z))


def main() -> None:
    """Fit once per rolling window, apply the post-processing variants and print the Brier scores."""
    cfg = train.load_config()
    margin = cfg["spike_margin"]
    index = train.make_index(cfg)
    df = rr.global_frame(cfg, index)
    res: dict[str, list[dict[str, float]]] = {}
    for start in rr.STARTS:
        tr = df[df["forecast_origin_utc"] + rr.LABEL_LAG <= start].reset_index(drop=True)
        in_window = (df["forecast_origin_utc"] >= start) & (df["forecast_origin_utc"] < start + pd.Timedelta(days=7))
        ev = df[in_window].reset_index(drop=True)
        mdl = train.fit(tr, cfg, start, verbose=False)
        base_pred = predict.predict_frame(mdl, ev, with_drivers=False)
        none_share = float((tr["dir"] == 0).mean())
        recent = tr[tr["forecast_origin_utc"] >= start - pd.Timedelta(days=RECENT_BASE_RATE_DAYS) - rr.LABEL_LAG]
        variants = {"base": base_pred}

        fixed_none = base_pred.copy()
        fixed_none["p_none"] = none_share
        rescale = (1 - none_share) / (fixed_none["p_up"] + fixed_none["p_down"])
        fixed_none["p_up"] *= rescale
        fixed_none["p_down"] *= rescale
        variants["A_none_fixed"] = fixed_none

        spike_defs = (
            ("p_spike_high", lambda d: d["y"] > d["spot_label"] + margin),
            ("p_spike_low", lambda d: d["y"] < d["spot_label"] - margin),
        )
        for col, is_spike in spike_defs:
            shift = logit(is_spike(recent).mean()) - logit(is_spike(tr).mean())
            for strength in SHIFT_STRENGTHS:
                shifted = variants.setdefault(f"B_{strength}", base_pred.copy())
                shifted[col] = sigmoid(logit(base_pred[col].to_numpy()) + strength * shift)
        for name, pred in variants.items():
            res.setdefault(name, []).append(rr.metrics(pred, ev, margin))
        print(start, "none share", round(none_share, 4), flush=True)

    base = pd.DataFrame(res["base"])
    for name, rows in res.items():
        r = pd.DataFrame(rows)
        n_spike_better = (r.brier_spike < base.brier_spike).sum()
        n_dir_better = (r.brier_dir < base.brier_dir).sum()
        spike_diff = (r.brier_spike - base.brier_spike).mean()
        dir_diff = (r.brier_dir - base.brier_dir).mean()
        print(
            f"{name:14s} spike {r.brier_spike.mean():.4f} ({n_spike_better}/8 better, diff {spike_diff:+.5f})"
            f"  dir {r.brier_dir.mean():.4f} ({n_dir_better}/8, diff {dir_diff:+.5f})"
        )


if __name__ == "__main__":
    main()
