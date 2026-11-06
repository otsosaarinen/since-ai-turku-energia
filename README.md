# Imbalance price forecast, 10 h ahead (Since AI 2026, Turku Energia)

LightGBM quantile / classification models forecasting the Finnish imbalance price for 40 quarter-hours from each
full-hour origin. Every feature is built from rows with `first_usable_origin_utc <= origin` only.

## Setup
```bash
# macOS only: LightGBM needs OpenMP
brew install libomp
uv sync
```
Put the organiser files here (not in git): `starter_package_v1/` (unzipped, read-only reference) and
`data/` containing `inputs.parquet`, `spot_nordpool.csv` (Nord Pool licence: hackathon use only), `actuals_validation.csv`.

## Run
```bash
uv run pytest -q                              # availability / leakage tests (20)
# 1. reproduce the organiser baseline on the validation period (writes outputs/baseline/validation)
uv run python -c "from src.baseline import *; run_validation_baseline('starter_package_v1','data','outputs/baseline/validation')"
cd outputs/baseline/validation && python -I ../../../starter_package_v1/score.py --submission forecast_backtest.csv \
  --actuals ../../../data/actuals_validation.csv --spike-margin 50 --output-dir score && cd ../../..
# 2. validation: train on data usable at 2026-09-06T21:00Z, forecast 7 Sep-4 Oct, score vs baseline
uv run scripts/run_validation.py
# 3. final: train up to the 4 Oct cut-off, forecast the 673 test origins, run the validator
uv run scripts/run_final.py                   # -> outputs/final/forecast_backtest.csv
python starter_package_v1/validate_submission.py --backtest outputs/final/forecast_backtest.csv \
  --origins starter_package_v1/forecast_origins.csv
```
Outputs: `outputs/validation/{forecast_backtest,backtest_vs_actual}.csv`, `outputs/validation/score/`
(`score_summary.md`, `score_by_horizon.csv`), `outputs/final/forecast_backtest.csv`.
All settings (periods, seed, LightGBM parameters) are in `configs/default.yaml`; seeds are fixed.
`scripts/train_cpu.sbatch` is a (not yet tested) LUMI-C Slurm job running the final step.

## Layout
`src/availability.py` availability filter | `features.py` features | `train.py` / `predict.py` models |
`evaluate.py` validator/scorer wrappers | `exports.py` frontend CSVs | `baseline.py` organiser baseline | `tests/`.

## Look at the forecasts
```bash
uv run scripts/show_origin.py 2026-09-20T09:00        # one origin in the terminal: forecast vs actual (validation month)
uv run --group app streamlit run app/app.py           # small local web viewer with a date/hour picker
```

## React viewer (web/)
```bash
uv run scripts/export_web_data.py        # CSV -> JSON for the viewer (re-run after new forecasts)
cd web && npm install && npm run dev     # open http://localhost:5173
```
