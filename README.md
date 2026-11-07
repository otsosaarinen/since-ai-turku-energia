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
uv run pytest -q                       # 23 tests: availability filter, leakage checks and input groups (about 20 s)
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
uv run scripts/run_variants.py         # the 7 model variants behind the viewer's input switches (about 12 min, optional)
uv run scripts/exp_postproc.py         # post-processing tests (none probability, spike base-rate shift) on the rolling windows (about 3 min)
uv run scripts/run_rolling.py --tag X  # 8 weekly validation windows (about 2 min); add --ref OTHER_TAG to compare with an earlier run
uv run python -I starter_package_v1/validate_submission.py --backtest outputs/final/forecast_backtest.csv --origins starter_package_v1/forecast_origins.csv
```
Validation outputs: `outputs/validation/forecast_backtest.csv`, `backtest_vs_actual.csv`, `score/` (`score_summary.md`, `score_by_horizon.csv`).
All settings (periods, seed, number of seeds, LightGBM parameters) are in `configs/default.yaml`.

## Look at the forecasts (web viewer)
```bash
./scripts/start_web.sh                           # starts the viewer at http://localhost:5173 (Ctrl+C stops it)
cd web && npx vitest run                         # 9 viewer tests
uv run scripts/show_origin.py 2026-09-20T09:00   # one validation origin in the terminal (UTC)
```
The viewer (`web/`, React + Recharts) is one screen without scrolling. It follows the Turku Energia graphic guidelines (white page, orange
as the accent colour, blue and grey structure with WCAG AA contrast, bold condensed capital headlines, plain wording), uses Finnish time and
dd/mm/yyyy, and has only two "i" tooltips (period buttons, key numbers; the chart legend explains the lines). What is on the screen, top to bottom:
- **Period buttons:** the validation month (with real prices) or the test forecast (without).
- **Two method boxes:** **Machine-learning model** (this repo's LightGBM forecasts) and **Harness prediction** (a second method, not connected yet). The
  highlighted box decides what the chart shows. To connect the harness, add its forecasts as `web/public/data/harness_validation.json` and
  `harness_final.json` in the same format as `validation.json` / `final.json` (`{name, hasActuals, cols, rows}`, see `src/exports.py`
  `web_payload`); until then its box shows a "not connected yet" message.
- **Summary strip:** a plain-language summary, the main drivers and the key numbers (chance of a high and a low price spike, chance the grid needs
  more power and, when real prices are known, the average error and how often the real price stayed in the likely range).
- **Chart (in the middle, as big as possible):** forecast, likely range (blue), real price (red), the forecast made 3 h earlier (grey) and a
  "Forecast made" line. The price axis is fixed (-50 to 350 EUR/MWh, from the data: the forecast line's 99.9th percentile and the likely range's 99th) so its numbers never move while time moves or plays;
  rare larger values run off the top and show in the hover tooltip. Above it: 1 h / 1 day steps that glide smoothly, a date list, a bar over the whole period, a **Play** button (speeds 1x, 3x,
  10x forecast hours per second; stops at the end). The **input switches** are stacked in a column to the left of the chart.
- **Input switches (Machine-learning model only):** turn Fingrid's day-ahead **solar**, **wind** and **consumption** forecasts on or off. The page cannot
  re-run the model, so each of the 8 combinations is a separately trained model computed beforehand with `uv run scripts/run_variants.py`
  (7 extra variants, about 12 minutes, files in `web/public/data/variants/`). A label shows the validation error of the chosen variant.
  Residual-load features combine all three forecasts, so they are removed whenever any switch is off. Real cloud or sunlight data is not in the model.

**Data for the viewer.** `start_web.sh` rebuilds `web/public/data/validation.json` and `final.json` from `outputs/` when that exists (the model
owner's machine); otherwise it uses the JSON files already in `web/public/data/`. All of `web/public/data/` is git-ignored (forecasts and real
imbalance prices, no spot prices). **On another laptop (e.g. a teammate's):** `git clone`, copy the whole `web/public/data/` folder from the model
owner (about 75 MB with `variants/`; without `variants/` the switches show "not computed yet") and run `./scripts/start_web.sh`. Only Node.js
is needed; no Python, data or model.
**On Windows** the `.sh` script does not run (double-clicking it only opens it in an editor). Use a terminal (PowerShell or the VS Code terminal) in the repo folder instead:
```
cd web
npm install
npm run dev
```
and open http://localhost:5173. `app/app.py` is an older, optional Streamlit viewer (`uv run --group app streamlit run app/app.py`).

## Layout
- `src/availability.py` availability filter (fast index, same result as the organiser's `rows_available_at`)
- `src/features.py` features per (origin, step) and the input groups the viewer can switch off | `src/train.py`, `src/predict.py` models |
  `src/evaluate.py` validator and scorer wrappers | `src/exports.py` viewer tables | `src/baseline.py` organiser baseline
- `scripts/` `run_validation.py`, `run_rolling.py`, `run_final.py`, `run_variants.py`, `exp_postproc.py`, `export_web_data.py`, `start_web.sh`, `show_origin.py`,
  `train_cpu.sbatch` (LUMI Slurm job for the final run; untested, LUMI is optional because local training takes about a minute)
- `web/` React viewer (`web/src/design-system/` = Turku Energia design components) | `tests/` Python tests | `configs/default.yaml` all model settings
