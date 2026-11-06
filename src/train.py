"""Model training.

Models (all LightGBM, CPU, fixed seed):
  * quantile regression p10 / p50 / p90 on  spread = imbalance - spot(target)  (or the level)
  * multiclass direction (down / none / up)
  * two binary classifiers for exceptional prices (> spot+margin, < spot-margin)

Number of boosting rounds per model is chosen on a time-ordered inner split (the last
``inner_valid_days`` of the training window, with an embargo so that no training target lies in
the inner-validation span) and the final model is refit on the whole training window.
"""
from __future__ import annotations

import argparse
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from .availability import AvailabilityIndex, load_all, to_utc
from .features import build_dataset, feature_columns

DIR_TO_CLASS = {-1: 0, 0: 1, 1: 2}   # down, none, up
HORIZON = pd.Timedelta(hours=10)
ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path = ROOT / "configs" / "default.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


def make_index(cfg: dict) -> AvailabilityIndex:
    return AvailabilityIndex(load_all(ROOT / cfg["paths"]["inputs"], ROOT / cfg["paths"]["spot"]))


def training_frame(index: AvailabilityIndex, cfg: dict, cutoff) -> pd.DataFrame:
    """All hourly training origins whose 40 labels are known (first_usable <= cutoff)."""
    cutoff = to_utc(cutoff)
    origins = pd.date_range(index.grid[0].ceil("h"), cutoff - HORIZON, freq="h")
    return build_dataset(index, origins, cfg, label_cutoff=cutoff)


def targets(df: pd.DataFrame, cfg: dict) -> dict[str, np.ndarray]:
    m = cfg["spike_margin"]
    spot = df["spot_label"].to_numpy()
    y = df["y"].to_numpy()
    base = spot if cfg["model"]["target"] == "spread" else 0.0
    return {
        "reg": y - base,
        "dir": df["dir"].map(DIR_TO_CLASS).to_numpy(),
        "hi": (y > spot + m).astype(int),
        "lo": (y < spot - m).astype(int),
    }


@dataclass
class Models:
    cfg: dict
    features: list[str]
    boosters: dict = field(default_factory=dict)
    best_iter: dict = field(default_factory=dict)
    offsets: dict = field(default_factory=lambda: {"p10": 0.0, "p90": 0.0})

    def params(self, objective: str, **extra) -> dict:
        p = dict(self.cfg["model"]["lgbm"])
        p.update(objective=objective, seed=self.cfg["seed"], deterministic=True, force_row_wise=True, **extra)
        return p


SPECS = {
    "p10": ("quantile", {"alpha": 0.1}, "reg"),
    "p50": ("quantile", {"alpha": 0.5}, "reg"),
    "p90": ("quantile", {"alpha": 0.9}, "reg"),
    "dir": ("multiclass", {"num_class": 3}, "dir"),
    "hi": ("binary", {}, "hi"),
    "lo": ("binary", {}, "lo"),
}


def inner_split(df: pd.DataFrame, cfg: dict, cutoff) -> tuple[np.ndarray, np.ndarray]:
    """Time-ordered train / inner-valid masks with an embargo of the 10 h horizon."""
    v0 = to_utc(cutoff) - pd.Timedelta(days=cfg["model"]["inner_valid_days"])
    o = df["forecast_origin_utc"]
    return (o + HORIZON <= v0).to_numpy(), (o >= v0).to_numpy()


def fit(df: pd.DataFrame, cfg: dict, cutoff, verbose: bool = True) -> Models:
    feats = feature_columns(df)
    mdl = Models(cfg, feats)
    T = targets(df, cfg)
    tr, va = inner_split(df, cfg, cutoff)
    X = df[feats]
    n_seeds = int(cfg["model"].get("n_seeds", 1))
    hl = cfg["model"].get("recency_halflife_days")
    age_days = (to_utc(cutoff) - df["forecast_origin_utc"]).dt.total_seconds().to_numpy() / 86400.0
    W = 0.5 ** (age_days / hl) if hl else np.ones(len(df))   # recent origins weigh more
    inner = {}
    for name, (obj, extra, tkey) in SPECS.items():
        p = mdl.params(obj, **extra)
        d_tr = lgb.Dataset(X[tr], T[tkey][tr], weight=W[tr])
        d_va = lgb.Dataset(X[va], T[tkey][va], weight=W[va], reference=d_tr)
        b = lgb.train(p, d_tr, cfg["model"]["rounds_max"], valid_sets=[d_va],
                      callbacks=[lgb.early_stopping(cfg["model"]["early_stopping"], verbose=False)])
        inner[name] = b
        best = max(30, int(b.best_iteration * 1.1))
        mdl.best_iter[name] = best
        # refit on the whole window; a few seeds are averaged to reduce variance
        mdl.boosters[name] = [lgb.train({**p, "seed": cfg["seed"] + i}, lgb.Dataset(X, T[tkey], weight=W), best)
                              for i in range(n_seeds)]
        if verbose:
            print(f"  {name}: inner best_iter={b.best_iteration} -> refit rounds={best} x{n_seeds} seeds")
    # CQR-style interval calibration on the inner holdout: shift p10/p90 so that the empirical
    # tail frequencies match 10 % / 10 % (models there were fit on earlier data only).
    q = {k: inner[k].predict(X[va], num_iteration=inner[k].best_iteration) for k in ("p10", "p90")}
    y = T["reg"][va]
    cap = float(cfg["model"].get("calib_cap", 40.0))
    if cfg["model"].get("calibrate_interval", True):
        mdl.offsets["p10"] = float(np.clip(_shift(q["p10"], y, 0.10), -cap, cap))
        mdl.offsets["p90"] = float(np.clip(_shift(q["p90"], y, 0.90), -cap, cap))
        if verbose:
            print(f"  interval calibration offsets (EUR/MWh): {mdl.offsets}  "
                  f"inner coverage before {(np.mean((y>=q['p10'])&(y<=q['p90']))):.3f}")
    return mdl


def _shift(pred: np.ndarray, y: np.ndarray, alpha: float) -> float:
    """Additive shift c so that mean(y <= pred + c) == alpha (conformal quantile correction)."""
    return float(np.quantile(y - pred, alpha))


def save(mdl: Models, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(mdl, f)


def load(path: str | Path) -> Models:
    with open(path, "rb") as f:
        return pickle.load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["validation", "final"], required=True)
    ap.add_argument("--config", default=str(ROOT / "configs" / "default.yaml"))
    a = ap.parse_args()
    cfg = load_config(a.config)
    cutoff = cfg["periods"]["validation_first_origin" if a.period == "validation" else "training_cutoff_label_origin"]
    index = make_index(cfg)
    df = training_frame(index, cfg, cutoff)
    print(f"{a.period}: label cut-off {cutoff}, {df['forecast_origin_utc'].nunique()} origins, {len(df)} rows")
    mdl = fit(df, cfg, cutoff)
    out = ROOT / cfg["paths"]["outputs"] / "models" / f"{a.period}.pkl"
    save(mdl, out)
    print("saved", out)


if __name__ == "__main__":
    main()
