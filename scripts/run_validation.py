"""Train on data usable at the first validation origin, forecast 7 Sep - 4 Oct, validate + score vs baseline.

usage: python scripts/run_validation.py [--config configs/default.yaml] [--tag NAME] [--set model.target=level ...]
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import evaluate, exports, predict, train  # noqa: E402


def apply_overrides(cfg, sets):
    for s in sets or []:
        k, v = s.split("=", 1)
        d = cfg
        parts = k.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = yaml_load(v)
    return cfg


def yaml_load(v):
    import yaml
    return yaml.safe_load(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "default.yaml"))
    ap.add_argument("--tag", default="validation")
    ap.add_argument("--set", action="append")
    a = ap.parse_args()
    cfg = apply_overrides(train.load_config(a.config), a.set)
    out = ROOT / cfg["paths"]["outputs"] / a.tag
    tpl = ROOT / cfg["paths"]["outputs"] / "baseline" / "validation"
    cutoff = cfg["periods"]["validation_first_origin"]
    t = time.time()
    index = train.make_index(cfg)
    df = train.training_frame(index, cfg, cutoff)
    print(f"training rows {len(df)} origins {df['forecast_origin_utc'].nunique()} "
          f"last origin {df['forecast_origin_utc'].max()}  ({time.time()-t:.0f}s)")
    mdl = train.fit(df, cfg, cutoff)
    train.save(mdl, out / "model.pkl")
    origins = pd.to_datetime(pd.read_csv(tpl / "forecast_origins.csv")["forecast_origin_utc"], utc=True)
    fc = predict.predict_origins(mdl, index, origins)
    sub = out / "forecast_backtest.csv"
    evaluate.write_submission(fc, sub, tpl / "sample_submission.csv")
    rc, txt = evaluate.validate(sub, tpl / "forecast_origins.csv")
    print(txt.splitlines()[0], "| errors line:", [l for l in txt.splitlines() if l.startswith("Errors")])
    rc, txt = evaluate.score(sub, ROOT / cfg["paths"]["actuals_validation"], out / "score",
                             tpl / "score" / "score_summary.csv")
    s = pd.read_csv(out / "score" / "score_summary.csv").iloc[0]
    b = pd.read_csv(tpl / "score" / "score_summary.csv").iloc[0]
    keys = ["mae_p50", "calibration_pinball_mean", "coverage_p10_p90", "brier_spike_mean", "brier_direction"]
    print(f"{'metric':28s}{'model':>10s}{'baseline':>10s}")
    for k in keys:
        print(f"{k:28s}{s[k]:10.4f}{b[k]:10.4f}")
    act = pd.read_csv(ROOT / cfg["paths"]["actuals_validation"])
    exports.backtest_vs_actual(fc, act).to_csv(out / "backtest_vs_actual.csv", index=False)
    print(f"total {time.time()-t:.0f}s")


if __name__ == "__main__":
    main()
