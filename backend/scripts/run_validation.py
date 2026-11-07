"""Train on data usable at the first validation origin, forecast 7 Sep - 4 Oct, validate + score vs baseline.

usage: uv run scripts/run_validation.py [--config configs/default.yaml] [--tag NAME] [--set model.target=level ...]
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from src import evaluate, exports, predict, train

ROOT = train.ROOT  # backend/: data, outputs and configs live below it
SCORE_KEYS = ["mae_p50", "calibration_pinball_mean", "coverage_p10_p90", "brier_spike_mean", "brier_direction"]


def main() -> None:
    """Train on labels usable at the first validation origin, forecast, validate and score against the baseline."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(train.DEFAULT_CONFIG))
    parser.add_argument("--tag", default="validation")
    parser.add_argument("--set", action="append")
    args = parser.parse_args()
    cfg = train.apply_overrides(train.load_config(args.config), args.set)
    out = ROOT / cfg["paths"]["outputs"] / args.tag
    template_dir = ROOT / cfg["paths"]["outputs"] / "baseline" / "validation"
    cutoff = cfg["periods"]["validation_first_origin"]
    started = time.time()
    index = train.make_index(cfg)
    df = train.training_frame(index, cfg, cutoff)
    print(
        f"training rows {len(df)} origins {df['forecast_origin_utc'].nunique()} "
        f"last origin {df['forecast_origin_utc'].max()}  ({time.time() - started:.0f}s)"
    )
    mdl = train.fit(df, cfg, cutoff)
    train.save(mdl, out / "model.pkl")
    origins = pd.to_datetime(pd.read_csv(template_dir / "forecast_origins.csv")["forecast_origin_utc"], utc=True)
    forecast = predict.predict_origins(mdl, index, origins)
    submission = out / "forecast_backtest.csv"
    evaluate.write_submission(forecast, submission, template_dir / "sample_submission.csv")
    _, validator_output = evaluate.validate(submission, template_dir / "forecast_origins.csv")
    lines = validator_output.splitlines()
    print(lines[0], "| errors line:", [line for line in lines if line.startswith("Errors")])
    actuals_path = ROOT / cfg["paths"]["actuals_validation"]
    evaluate.score(submission, actuals_path, out / "score", template_dir / "score" / "score_summary.csv")
    model_scores = pd.read_csv(out / "score" / "score_summary.csv").iloc[0]
    baseline_scores = pd.read_csv(template_dir / "score" / "score_summary.csv").iloc[0]
    print(f"{'metric':28s}{'model':>10s}{'baseline':>10s}")
    for key in SCORE_KEYS:
        print(f"{key:28s}{model_scores[key]:10.4f}{baseline_scores[key]:10.4f}")
    exports.backtest_vs_actual(forecast, pd.read_csv(actuals_path)).to_csv(out / "backtest_vs_actual.csv", index=False)
    print(f"total {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
