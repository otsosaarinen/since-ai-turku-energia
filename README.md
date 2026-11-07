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
- What validation and test mean, how the model is trained and why, how points work: `REPORT.md`. Every experiment with numbers: `EXPERIMENTS.md`. Data sources and licences: `SOURCES.md`.

## Two ways to use this repo
- **Only look at the forecasts (no training):** see "Look at the forecasts" below. You need Node.js and two ready-made files from the model owner.
- **Reproduce everything, including training the model:** the repo contains **no data and no trained model**, because the data is licensed
  (Nord Pool spot prices: hackathon use only, never commit or share) and models are rebuilt in about a minute. You train it yourself on your
  own laptop (CPU only, no GPU needed) by following the steps below.

## Reproduce from scratch (you train the model yourself)
Requirements: macOS or Linux, [git](https://git-scm.com), [uv](https://docs.astral.sh/uv/) (installs Python for you) and, for the viewer, Node.js 20+.
On macOS also run `brew install libomp` once (LightGBM needs OpenMP).

**1. Get the code**
```bash
git clone https://github.com/otsosaarinen/since-ai-turku-energia.git
cd since-ai-turku-energia
```

**2. Get the organisers' data package** (not in git). Download `starter_package_v1.zip` and `SHA256SUMS.txt` from the Since AI / Turku Energia
challenge page into any folder outside the repo (below: `~/Downloads/TurkuEnergia_SinceAI2026`), then, from the repo folder:
```bash
DL=~/Downloads/TurkuEnergia_SinceAI2026                # the folder where you saved the organisers' files
(cd "$DL" && shasum -a 256 -c SHA256SUMS.txt --ignore-missing)    # every line should end with: OK
unzip "$DL/starter_package_v1.zip"                     # creates starter_package_v1/ here (read-only reference)
mkdir -p data
cp starter_package_v1/data/inputs.parquet starter_package_v1/data/spot_nordpool.csv starter_package_v1/data/actuals_validation.csv data/
```
Never commit `data/`, `starter_package_v1/` or `outputs/` (they are git-ignored; keep it that way, the repo is public).

**3. Install**
```bash
uv sync
uv run pytest -q                       # 21 tests: availability filter and leakage checks (about 20 s)
```

**4. Reproduce the organisers' baseline** (once; the validation step compares against it)
```bash
uv run python -c "from src.baseline import *; run_validation_baseline('starter_package_v1','data','outputs/baseline/validation')"
cd outputs/baseline/validation && uv run python -I ../../../starter_package_v1/score.py --submission forecast_backtest.csv \
  --actuals ../../../data/actuals_validation.csv --spike-margin 50 --output-dir score && cd ../../..
```

**5. Train and test on the validation month** (about 1 minute). This trains the model on data available before 7 Sep, forecasts 7 Sep - 4 Oct and scores it against the baseline:
```bash
uv run scripts/run_validation.py
```
Expected result (reproducible, seeds are fixed): MAE 43.2144, pinball 12.4164, coverage 0.7869, spike Brier 0.0967, direction Brier 0.4121 (baseline 66.2033 / 24.1776 / 0.6829 / 0.1132 / 0.4509).

**6. Train the final model and make the submission file** (about 1 minute). This trains on everything up to 4 Oct, forecasts the 673 test origins and runs the organisers' validator:
```bash
uv run scripts/run_final.py
```
It ends with `VALIDATION PASSED` and `Errors: 0`. The submission file is `outputs/final/forecast_backtest.csv`.

**Where is the model?** Training happens inside steps 5 and 6; the fitted models are saved as `outputs/validation/model.pkl` and `outputs/final/model.pkl` (git-ignored). Delete `outputs/` and rerun to retrain from scratch.

**Other commands**
```bash
uv run scripts/run_rolling.py --tag X  # 8 weekly validation windows (about 2 min); add --ref OTHER_TAG to compare with an earlier run
uv run python -I starter_package_v1/validate_submission.py --backtest outputs/final/forecast_backtest.csv --origins starter_package_v1/forecast_origins.csv
```
Validation outputs: `outputs/validation/forecast_backtest.csv`, `backtest_vs_actual.csv`, `score/` (`score_summary.md`, `score_by_horizon.csv`).
All settings (periods, seed, number of seeds, LightGBM parameters) are in `configs/default.yaml`.

## Look at the forecasts
```bash
./scripts/start_web.sh                   # starts the viewer at http://localhost:5173 (Ctrl+C stops it)
cd web && npx vitest run                 # viewer test
uv run scripts/show_origin.py 2026-09-20T09:00   # one validation origin in the terminal (UTC)
```
The viewer (`web/`, React + Recharts, styled with the Turku Energia design system in `web/src/design-system/`) is one screen without scrolling:
the price chart (p50, p10-p90 band, real price, the forecast made 3 h earlier, a "now" line) takes most of the space, with time controls above it
(1 h / 1 day steps, date list, a bar over the whole period) and the key numbers, a short summary and the top three drivers on the left.
It uses Finnish time and dd/mm/yyyy, and switches between the validation month (with real prices) and the test forecast (without).

`start_web.sh` rebuilds the viewer data from `outputs/` when that exists (model owner's machine); otherwise it uses ready-made
`web/public/data/validation.json` and `final.json`. **On another laptop (e.g. a teammate's):** `git clone`, put those two files (from the
model owner; they are not in git) into `web/public/data/`, and run `./scripts/start_web.sh`. Only Node.js is needed; no Python, data or model.

`app/app.py` is an older, optional Streamlit viewer (`uv run --group app streamlit run app/app.py`).

## Layout
- `src/availability.py` availability filter (fast index, same result as the organiser's `rows_available_at`)
- `src/features.py` features per (origin, step) | `src/train.py`, `src/predict.py` models | `src/evaluate.py` validator and scorer wrappers
- `web/` React viewer styled with the Turku Energia design system (`web/src/design-system/`)
- `src/exports.py` `backtest_vs_actual` table | `src/baseline.py` organiser baseline | `tests/` | `configs/` | `scripts/` | `web/` viewer
- `scripts/train_cpu.sbatch` LUMI Slurm job for the final run (untested; LUMI is optional, local training takes about a minute)
