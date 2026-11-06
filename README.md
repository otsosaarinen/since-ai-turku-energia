# Imbalance price forecast, 10 h ahead (Since AI 2026, Turku Energia)

Forecasts the Finnish imbalance price (`fi_imbalance_price`) for 40 quarter-hours (10 h) from every full-hour origin:
p10 / p50 / p90, direction probabilities (up / down / none) and spike probabilities (price > spot + 50 or < spot - 50).
Every feature is built only from rows with `first_usable_origin_utc <= origin`.

## Current model and results
- **Model:** LightGBM (CPU), six models: quantile p10 / p50 / p90 on `imbalance - spot`, a 3-class direction model and two
  binary spike models. Small trees (8 leaves), extra-trees mode, 6 seeds averaged, p10/p90 calibrated on a held-out slice.
- **Validation month (7 Sep - 4 Oct), baseline vs model:** MAE 66.20 vs 43.21, pinball 24.18 vs 12.42, coverage 0.683 vs 0.787,
  spike Brier 0.1132 vs 0.0967, direction Brier 0.4509 vs 0.4121.
- **8 rolling weekly windows (mean):** MAE 37.5, pinball 9.88, coverage 0.78, spike 0.0937, direction 0.4173.
- Details and reasoning: `REPORT.md`. Every experiment with numbers: `EXPERIMENTS.md`. Data sources and licences: `SOURCES.md`.

## Setup
Requires [uv](https://docs.astral.sh/uv/) and, for the viewer, Node 20+.
```bash
brew install libomp     # macOS only: LightGBM needs OpenMP
uv sync
```
Put the organiser files here (they are not in git): `starter_package_v1/` (unzipped, read-only reference) and `data/`
containing `inputs.parquet`, `spot_nordpool.csv` (Nord Pool licence: hackathon use only, never commit or share) and
`actuals_validation.csv`.

## Run
```bash
uv run pytest -q                       # 21 tests: availability filter and leakage checks
uv run scripts/run_validation.py       # train on data usable at 2026-09-06T21:00Z, forecast 7 Sep - 4 Oct, score vs baseline
uv run scripts/run_rolling.py --tag X  # 8 weekly windows; add --ref OTHER_TAG to compare with an earlier run
uv run scripts/run_final.py            # train up to the 4 Oct cut-off, forecast the 673 test origins, run the validator
```
The submission file is `outputs/final/forecast_backtest.csv`. Check it yourself with
`uv run python -I starter_package_v1/validate_submission.py --backtest outputs/final/forecast_backtest.csv --origins starter_package_v1/forecast_origins.csv`.
Validation outputs: `outputs/validation/forecast_backtest.csv`, `backtest_vs_actual.csv`, `score/` (`score_summary.md`, `score_by_horizon.csv`).

To reproduce the organiser's baseline on the validation month:
```bash
uv run python -c "from src.baseline import *; run_validation_baseline('starter_package_v1','data','outputs/baseline/validation')"
cd outputs/baseline/validation && uv run python -I ../../../starter_package_v1/score.py --submission forecast_backtest.csv \
  --actuals ../../../data/actuals_validation.csv --spike-margin 50 --output-dir score && cd ../../..
```
All settings (periods, seed, number of seeds, LightGBM parameters) are in `configs/default.yaml`; seeds are fixed.

## Look at the forecasts
```bash
uv run scripts/export_web_data.py        # forecast CSVs -> JSON for the viewer (re-run after a new forecast)
cd web && npm install && npm run dev     # open http://localhost:5173 (Finnish time, date bar over the whole period)
cd web && npx vitest run                 # viewer test
uv run scripts/show_origin.py 2026-09-20T09:00   # one validation origin in the terminal (UTC)
```
`app/app.py` is an older, optional Streamlit viewer (`uv run --group app streamlit run app/app.py`).

## Layout
- `src/availability.py` availability filter (fast index, same result as the organiser's `rows_available_at`)
- `src/features.py` features per (origin, step) | `src/train.py`, `src/predict.py` models | `src/evaluate.py` validator and scorer wrappers
- `src/exports.py` `backtest_vs_actual` table | `src/baseline.py` organiser baseline | `tests/` | `configs/` | `scripts/` | `web/` viewer
- `scripts/train_cpu.sbatch` LUMI Slurm job for the final run (untested; LUMI is optional, local training takes about a minute)
