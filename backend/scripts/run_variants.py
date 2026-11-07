"""Train and forecast every on/off combination of the viewer's input toggles (solar, wind, consumption forecast).

Each variant is a separately trained model WITHOUT the switched-off input group (same settings and seeds
otherwise; residual-load features are removed whenever any group is off because they combine all three).
Outputs (git-ignored, no spot prices):
  frontend/public/data/variants/{validation,final}_<key>.json
      key = three digits solar/wind/consumption, 1 = on, 0 = off ("111" = the normal model, served by
      validation.json / final.json)
  frontend/public/data/variants/index.json
      validation metrics of every variant (shown next to the toggles)
usage: uv run scripts/run_variants.py [--keys 011 101 ...]      (all 7 variants take about 12 minutes)
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import time

import pandas as pd

from src import exports, predict, train
from src.features import TOGGLE_GROUPS, build_dataset, dropped_features, feature_columns

ROOT = train.ROOT  # backend/: data, outputs and configs live below it
REPO_ROOT = ROOT.parent  # the folder holding backend/ and frontend/

GROUPS = list(TOGGLE_GROUPS)  # solar, wind, consumption
OUT = REPO_ROOT / "frontend" / "public" / "data" / "variants"


def main() -> None:
    """Train and export every requested on/off combination of the input groups."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", nargs="*", help="only these variants, e.g. 011 101")
    args = parser.parse_args()
    cfg = train.load_config()
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    index = train.make_index(cfg)
    val_cutoff = cfg["periods"]["validation_first_origin"]
    final_cutoff = cfg["periods"]["training_cutoff_label_origin"]
    df_val = train.training_frame(index, cfg, val_cutoff)
    df_fin = train.training_frame(index, cfg, final_cutoff)
    val_origins = pd.date_range(val_cutoff, cfg["periods"]["validation_last_origin"], freq="h")
    test_origins = pd.to_datetime(pd.read_csv(ROOT / cfg["paths"]["origins_test"])["forecast_origin_utc"], utc=True)
    X_val, X_fin = build_dataset(index, val_origins, cfg), build_dataset(index, test_origins, cfg)
    actuals = pd.read_csv(ROOT / cfg["paths"]["actuals_validation"])
    all_cols = feature_columns(df_val)
    print(
        f"frames ready ({time.time() - started:.0f}s): "
        f"{len(val_origins)} validation origins, {len(test_origins)} test origins",
        flush=True,
    )

    idx_path = OUT / "index.json"
    index_json = (
        json.loads(idx_path.read_text()) if idx_path.exists() else {"groups": GROUPS, "metrics": {}, "dropped": {}}
    )
    base = pd.read_csv(
        ROOT / "outputs/validation/backtest_vs_actual.csv", parse_dates=["forecast_origin_utc", "delivery_start_utc"]
    )
    index_json["metrics"]["111"], index_json["dropped"]["111"] = exports.quick_metrics(base), 0

    for combo in itertools.product([1, 0], repeat=len(GROUPS)):
        key = "".join(map(str, combo))
        off = [group for group, on in zip(GROUPS, combo, strict=True) if not on]
        if not off or (args.keys and key not in args.keys):
            continue
        cfg_v = copy.deepcopy(cfg)
        cfg_v["model"]["drop_features"] = dropped_features(all_cols, off)
        for name, df, cut, X in (("validation", df_val, val_cutoff, X_val), ("final", df_fin, final_cutoff, X_fin)):
            fc = predict.predict_frame(train.fit(df, cfg_v, cut, verbose=False), X)
            if name == "validation":
                fc = exports.backtest_vs_actual(fc, actuals)
                index_json["metrics"][key] = exports.quick_metrics(fc)
                index_json["dropped"][key] = len(cfg_v["model"]["drop_features"])
            (OUT / f"{name}_{key}.json").write_text(
                json.dumps(exports.web_payload(fc, f"{name}_{key}"), separators=(",", ":"))
            )
        m = index_json["metrics"][key]
        print(
            f"{key} (off: {', '.join(off)}; {index_json['dropped'][key]} features removed): "
            f"validation MAE {m['mae']:.2f} pinball {m['pinball']:.2f} ({time.time() - started:.0f}s)",
            flush=True,
        )
        idx_path.write_text(json.dumps(index_json))
    idx_path.write_text(json.dumps(index_json))
    print("done", f"{time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
