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

DIR_TO_CLASS = {-1: 0, 0: 1, 1: 2}  # down, none, up
HORIZON = pd.Timedelta(hours=10)
ROOT = Path(__file__).resolve().parents[1]  # backend/: data, outputs and configs live below it
DEFAULT_CONFIG = ROOT / "configs" / "default.yaml"
SECONDS_PER_DAY = 86400.0
MIN_ROUNDS = 30  # floor for the refit rounds so a tiny inner optimum cannot under-fit the final model
ROUNDS_MARGIN = 1.1  # the final model sees more data than the inner split, so it gets 10 % more rounds
DEFAULT_CALIB_CAP = 40.0  # EUR/MWh, largest allowed conformal shift of p10/p90
QUANTILE_LOW, QUANTILE_HIGH = 0.10, 0.90


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """Read the YAML config (periods, seeds, LightGBM settings)."""
    return yaml.safe_load(Path(path).read_text())


def apply_overrides(cfg: dict, assignments: list[str] | None) -> dict:
    """Apply ``--set a.b.key=value`` strings to ``cfg`` in place (values parsed as YAML) and return it."""
    for assignment in assignments or []:
        dotted_key, raw_value = assignment.split("=", 1)
        *parents, leaf = dotted_key.split(".")
        node = cfg
        for part in parents:
            node = node[part]
        node[leaf] = yaml.safe_load(raw_value)
    return cfg


def make_index(cfg: dict) -> AvailabilityIndex:
    """Availability index over the organiser inputs plus the (hackathon-only) spot series."""
    return AvailabilityIndex(load_all(ROOT / cfg["paths"]["inputs"], ROOT / cfg["paths"]["spot"]))


def training_frame(index: AvailabilityIndex, cfg: dict, cutoff: pd.Timestamp | str) -> pd.DataFrame:
    """All hourly training origins whose 40 labels are known (first_usable <= cutoff)."""
    cutoff = to_utc(cutoff)
    origins = pd.date_range(index.grid[0].ceil("h"), cutoff - HORIZON, freq="h")
    return build_dataset(index, origins, cfg, label_cutoff=cutoff)


def targets(df: pd.DataFrame, cfg: dict) -> dict[str, np.ndarray]:
    """Training targets per model key: regression (spread or level), direction class, spike flags."""
    margin = cfg["spike_margin"]
    spot = df["spot_label"].to_numpy()
    y = df["y"].to_numpy()
    base = spot if cfg["model"]["target"] == "spread" else 0.0
    return {
        "reg": y - base,
        "dir": df["dir"].map(DIR_TO_CLASS).to_numpy(),
        "hi": (y > spot + margin).astype(int),
        "lo": (y < spot - margin).astype(int),
    }


@dataclass
class Models:
    """Everything needed to predict: config, feature list, boosters (several seeds each) and interval offsets."""

    cfg: dict
    features: list[str]
    boosters: dict[str, list[lgb.Booster]] = field(default_factory=dict)
    best_iter: dict[str, int] = field(default_factory=dict)
    offsets: dict[str, float] = field(default_factory=lambda: {"p10": 0.0, "p90": 0.0})

    def params(self, objective: str, **extra: object) -> dict:
        """LightGBM parameters for one model; seed and determinism flags are fixed for reproducibility."""
        params = dict(self.cfg["model"]["lgbm"])
        params.update(objective=objective, seed=self.cfg["seed"], deterministic=True, force_row_wise=True, **extra)
        return params


# model key -> (LightGBM objective, extra params, key into targets())
SPECS: dict[str, tuple[str, dict, str]] = {
    "p10": ("quantile", {"alpha": 0.1}, "reg"),
    "p50": ("quantile", {"alpha": 0.5}, "reg"),
    "p90": ("quantile", {"alpha": 0.9}, "reg"),
    "dir": ("multiclass", {"num_class": 3}, "dir"),
    "hi": ("binary", {}, "hi"),
    "lo": ("binary", {}, "lo"),
}


def inner_split(df: pd.DataFrame, cfg: dict, cutoff: pd.Timestamp | str) -> tuple[np.ndarray, np.ndarray]:
    """Time-ordered train / inner-valid masks with an embargo of the 10 h horizon."""
    valid_start = to_utc(cutoff) - pd.Timedelta(days=cfg["model"]["inner_valid_days"])
    origin = df["forecast_origin_utc"]
    return (origin + HORIZON <= valid_start).to_numpy(), (origin >= valid_start).to_numpy()


def fit(df: pd.DataFrame, cfg: dict, cutoff: pd.Timestamp | str, verbose: bool = True) -> Models:
    """Train all six models: rounds from the inner split, refit on everything, then calibrate p10/p90."""
    drop = set(cfg["model"].get("drop_features") or [])  # features switched off (viewer toggles / ablations)
    feats = [f for f in feature_columns(df) if f not in drop]
    mdl = Models(cfg, feats)
    target_arrays = targets(df, cfg)
    train_mask, valid_mask = inner_split(df, cfg, cutoff)
    X = df[feats]
    n_seeds = int(cfg["model"].get("n_seeds", 1))
    halflife = cfg["model"].get("recency_halflife_days")
    age_days = (to_utc(cutoff) - df["forecast_origin_utc"]).dt.total_seconds().to_numpy() / SECONDS_PER_DAY
    weights = 0.5 ** (age_days / halflife) if halflife else np.ones(len(df))  # recent origins weigh more
    inner: dict[str, lgb.Booster] = {}
    for name, (objective, extra, target_key) in SPECS.items():
        target = target_arrays[target_key]
        params = mdl.params(objective, **extra)
        d_train = lgb.Dataset(X[train_mask], target[train_mask], weight=weights[train_mask])
        d_valid = lgb.Dataset(X[valid_mask], target[valid_mask], weight=weights[valid_mask], reference=d_train)
        booster = lgb.train(
            params,
            d_train,
            cfg["model"]["rounds_max"],
            valid_sets=[d_valid],
            callbacks=[lgb.early_stopping(cfg["model"]["early_stopping"], verbose=False)],
        )
        inner[name] = booster
        rounds = max(MIN_ROUNDS, int(booster.best_iteration * ROUNDS_MARGIN))
        mdl.best_iter[name] = rounds
        # refit on the whole window; a few seeds are averaged to reduce variance
        mdl.boosters[name] = [
            lgb.train({**params, "seed": cfg["seed"] + i}, lgb.Dataset(X, target, weight=weights), rounds)
            for i in range(n_seeds)
        ]
        if verbose:
            print(f"  {name}: inner best_iter={booster.best_iteration} -> refit rounds={rounds} x{n_seeds} seeds")
    # CQR-style interval calibration on the inner holdout: shift p10/p90 so that the empirical
    # tail frequencies match 10 % / 10 % (models there were fit on earlier data only).
    inner_pred = {k: inner[k].predict(X[valid_mask], num_iteration=inner[k].best_iteration) for k in ("p10", "p90")}
    y_valid = target_arrays["reg"][valid_mask]
    cap = float(cfg["model"].get("calib_cap", DEFAULT_CALIB_CAP))
    if cfg["model"].get("calibrate_interval", True):
        mdl.offsets["p10"] = float(np.clip(_shift(inner_pred["p10"], y_valid, QUANTILE_LOW), -cap, cap))
        mdl.offsets["p90"] = float(np.clip(_shift(inner_pred["p90"], y_valid, QUANTILE_HIGH), -cap, cap))
        if verbose:
            inside = np.mean((y_valid >= inner_pred["p10"]) & (y_valid <= inner_pred["p90"]))
            print(f"  interval calibration offsets (EUR/MWh): {mdl.offsets}  inner coverage before {inside:.3f}")
    return mdl


def _shift(pred: np.ndarray, y: np.ndarray, alpha: float) -> float:
    """Additive shift c so that mean(y <= pred + c) == alpha (conformal quantile correction)."""
    return float(np.quantile(y - pred, alpha))


def save(mdl: Models, path: str | Path) -> None:
    """Pickle the trained models, creating the folder if needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(mdl, fh)


def load(path: str | Path) -> Models:
    """Load a model saved by ``save`` (pickle: only open files this project wrote itself)."""
    with open(path, "rb") as fh:
        return pickle.load(fh)  # own artefact, never untrusted input


def main() -> None:
    """CLI: train one period's model and save it to outputs/models/."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["validation", "final"], required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    cfg = load_config(args.config)
    key = "validation_first_origin" if args.period == "validation" else "training_cutoff_label_origin"
    cutoff = cfg["periods"][key]
    index = make_index(cfg)
    df = training_frame(index, cfg, cutoff)
    print(f"{args.period}: label cut-off {cutoff}, {df['forecast_origin_utc'].nunique()} origins, {len(df)} rows")
    mdl = fit(df, cfg, cutoff)
    out = ROOT / cfg["paths"]["outputs"] / "models" / f"{args.period}.pkl"
    save(mdl, out)
    print("saved", out)


if __name__ == "__main__":
    main()
