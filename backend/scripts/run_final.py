"""Final run: train on everything usable at the 4 Oct cut-off, forecast the 673 test origins.

Writes outputs/final/forecast_backtest.csv, then runs the organiser validator.
usage: uv run scripts/run_final.py
"""

from __future__ import annotations

import pandas as pd

from src import evaluate, predict, train


def main() -> None:
    """Train the final model and write the validated submission file."""
    cfg = train.load_config()
    out = train.ROOT / cfg["paths"]["outputs"] / "final"
    index = train.make_index(cfg)
    cutoff = cfg["periods"]["training_cutoff_label_origin"]
    df = train.training_frame(index, cfg, cutoff)
    print(
        f"final training: {df['forecast_origin_utc'].nunique()} origins, {len(df)} rows, "
        f"last origin {df['forecast_origin_utc'].max()}"
    )
    assert df["delivery_start_utc"].max() < pd.Timestamp(cutoff), "training target after the cut-off!"
    mdl = train.fit(df, cfg, cutoff)
    train.save(mdl, out / "model.pkl")
    origins_path = train.ROOT / cfg["paths"]["origins_test"]
    origins = pd.to_datetime(pd.read_csv(origins_path)["forecast_origin_utc"], utc=True)
    forecast = predict.predict_origins(mdl, index, origins)
    submission = out / "forecast_backtest.csv"
    evaluate.write_submission(forecast, submission, train.ROOT / cfg["paths"]["sample_submission"])
    _, validator_output = evaluate.validate(submission, origins_path)
    print(validator_output)


if __name__ == "__main__":
    main()
