# CLAUDE.md — Turku Energia imbalance price forecast (Since AI 2026)

Deadline: Sun 8 Nov 2026, 10:00. Forecast Finnish `fi_imbalance_price` 40 quarter-hours (10 h) ahead from every
full-hour origin; backtest 5 Oct–1 Nov 2026 = 673 origins x 40 = 26,920 rows -> `forecast_backtest.csv`. All data in UTC;
the web viewer shows Finnish time. The user owns the model work; teammates build the frontend. Docs: README.md (how to run),
REPORT.md (reasoning + metrics), EXPERIMENTS.md (every test with numbers), SOURCES.md (data and licences).

## HARD RULES (violation = score 0 / code audited)
- At origin t use a row only if `first_usable_origin_utc <= t`. Build every feature from `AvailabilityIndex.at(origin)`
  (src/availability.py) ONLY; compute lags/rolling/latest AFTER filtering. Never touch the unfiltered table.
- Train only on 1 Jun–4 Oct 2026. Never use test-period (after 4 Oct) rows or labels. Validation: train only with
  labels usable at the first validation origin (2026-09-06T21:00Z). Labels go through `AvailabilityIndex.labels(..., known_at=cutoff)`.
  A training origin o is usable at cut-off c only if o + 11 h <= c (all 40 labels published).
- Target quarter-hours' own actuals are never features. aFRR series are sparse: no row = no activation; never forward-fill.
- The briefing PDF (~/Downloads, slides 11 and 25) is the authority: extra open/paid data is allowed if sources and licences are
  listed, but test-period data is never used for training. No Open-Meteo Historical Forecast API.
- `data/spot_nordpool.csv` (Nord Pool) is hackathon-only: never print its rows, commit, share, or export spot values.
  `data/`, `outputs/`, `starter_package_v1/`, `*.csv`, `*.parquet`, model files are gitignored. Delete the data after the event.
- `starter_package_v1/` is read-only reference. Write all code outside it.
- Do not commit/push unless the user asks.

## Commands (uv project: `uv sync`, then `uv run ...`)
- `uv run pytest -q` (21 tests) and `cd web && npx vitest run` (1 test).
- `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` -> outputs/X/ (forecast, score vs baseline, backtest_vs_actual).
- `uv run scripts/run_rolling.py [--tag X] [--ref TAG] [--set key=value ...]` -> 8 weekly windows, features cached; judge changes here.
- `uv run scripts/run_final.py` -> outputs/final/forecast_backtest.csv and runs the organiser validator.
- Organiser tools: `uv run python -I starter_package_v1/{validate_submission,score,make_templates}.py`.
- Viewer: `uv run scripts/export_web_data.py`, then `cd web && npm run dev` (http://localhost:5173). Streamlit `app/` is optional/older.
- LightGBM on macOS needed `brew install libomp` (done).

## Model (configs/default.yaml)
Target = imbalance - spot(target) ("spread"). Six LightGBM models: quantile p10/p50/p90, multiclass direction (down/none/up),
two binary spike models (+-50 vs spot). 8 leaves, extra-trees, 6 seeds averaged, rounds from early stopping on a time-ordered inner
split (last 14 d, 10 h embargo) then refit on all; p10/p90 shifted by conformal offsets from that split. Post-processing: sort
quantiles, renormalise direction, scale spikes so high+low <= 1. `top_drivers` = grouped SHAP of p50; `data_cutoff_utc` = max
first_usable among cells in the window (usually == origin).

## Current results
- Validation month (baseline -> model): MAE 66.20 -> 43.21, pinball 24.18 -> 12.42, coverage 0.683 -> 0.787,
  spike Brier 0.1132 -> 0.0967, direction Brier 0.4509 -> 0.4121. Baseline reproduced exactly via src/baseline.py.
- 8 rolling windows (mean): MAE 37.5, pinball 9.88, coverage 0.78, spike 0.0937, direction 0.4173.
- Real skill vs trivial forecasts: MAE only ~1.1 better than "spot + typical spread" (38.7); interval 19 %, spike 14 %,
  direction 9 % better than constants. Spread autocorrelation is ~0 beyond 1 h, so skill comes from day-ahead structure
  (spot, consumption/wind/solar forecasts and their changes) and direction, not from recent prices.
- No gain from: tree size, regularisation, recency weighting, level target, seasonal same-time-of-day features, shrinking p50.
  Details in EXPERIMENTS.md.

## Status (6 Nov 2026 evening)
- Submission `outputs/final/forecast_backtest.csv` exists and passes the validator (0 errors, 0 warnings).
- Git: two commits, working tree clean when last checked; nothing licensed is tracked. Later doc edits are uncommitted until the user asks.
- The React viewer was checked in a browser by the user. The alerts feature was built and then removed at the user's request.
- LUMI: not set up; the user has no access sorted yet and training is fast locally. `scripts/train_cpu.sbatch` is untested with a
  placeholder project ID. If asked: run `lumi-workspaces` for the project ID, then give rsync commands excluding .git/.venv/outputs.

## Next ideas (ranked, none started)
1. Direction-aware price model (up/down regime prices mixed by P(direction)). 2. More direction features.
3. Spike probability calibration (September base-rate shift). 4. Slides (5-8), demo script and report polish: the jury part is 20 points.
Open-Meteo Single Runs only with the publication delay added; extra pre-June history was judged not worth the risk (EXPERIMENTS.md).
