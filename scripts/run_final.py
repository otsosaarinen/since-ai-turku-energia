"""Final run: train on everything usable at the 4 Oct cut-off, forecast the 673 test origins.

Writes outputs/final/forecast_backtest.csv, then runs the organiser validator.
usage: python scripts/run_final.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import evaluate, predict, train  # noqa: E402

cfg = train.load_config()
out = ROOT / cfg["paths"]["outputs"] / "final"
index = train.make_index(cfg)
cutoff = cfg["periods"]["training_cutoff_label_origin"]
df = train.training_frame(index, cfg, cutoff)
print(f"final training: {df['forecast_origin_utc'].nunique()} origins, {len(df)} rows, "
      f"last origin {df['forecast_origin_utc'].max()}")
assert df["delivery_start_utc"].max() < pd.Timestamp(cutoff), "training target after the cut-off!"
mdl = train.fit(df, cfg, cutoff)
train.save(mdl, out / "model.pkl")
origins = pd.to_datetime(pd.read_csv(ROOT / cfg["paths"]["origins_test"])["forecast_origin_utc"], utc=True)
fc = predict.predict_origins(mdl, index, origins)
sub = out / "forecast_backtest.csv"
evaluate.write_submission(fc, sub, ROOT / cfg["paths"]["sample_submission"])
rc, txt = evaluate.validate(sub, ROOT / cfg["paths"]["origins_test"])
print(txt)
