# CLAUDE.md — Turku Energia imbalance price forecast (Since AI 2026)

Deadline: Sun 8 Nov 2026, 10:00. Forecast Finnish `fi_imbalance_price` 40 quarter-hours (10 h) ahead from every
full-hour origin; backtest 5 Oct–1 Nov 2026 = 673 origins x 40 = 26,920 rows -> `forecast_backtest.csv`. All UTC.

## HARD RULES (violation = score 0 / code audited)
- At origin t use a row only if `first_usable_origin_utc <= t`. Build every feature from `AvailabilityIndex.at(origin)`
  (src/availability.py) ONLY; compute lags/rolling/latest AFTER filtering. Never touch the unfiltered table.
- Train only on 1 Jun–4 Oct 2026. Never use test-period (after 4 Oct) rows or labels. Validation: train only with
  labels usable at the first validation origin (2026-09-06T21:00Z). Labels go through `AvailabilityIndex.labels(..., known_at=cutoff)`.
- Training origins need all 40 targets known by the cutoff. Target quarter-hours' own actuals are never features.
- aFRR series are sparse: no row = no activation; never forward-fill. Missing stays missing.
- No Open-Meteo Historical Forecast API. Every external source goes into SOURCES.md with licence.
- `data/spot_nordpool.csv` (Nord Pool) is hackathon-only: never print its rows, commit, share, or export spot values.
  `data/`, `outputs/`, `starter_package_v1/`, `*.csv`, `*.parquet` are gitignored. Delete data after the event.
- `starter_package_v1/` is read-only reference (chmod a-w). Write all code outside it. Downloads folder is untouched.
- Do not commit/push unless the user asks.

## Layout / commands (uv project; `uv sync`, then `uv run ...`)
- src/availability.py (fast index == organiser rows_available_at), features.py, train.py, predict.py, evaluate.py,
  exports.py (backtest_vs_actual), baseline.py (ported organiser baseline).
- configs/default.yaml: periods, seeds, LightGBM params. tests/: `uv run pytest -q` (20 tests: availability equivalence,
  cut-off <= origin, features unchanged when future rows removed/corrupted, label cut-off).
- `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` -> outputs/X/ (forecast, score, backtest_vs_actual).
- `uv run scripts/run_final.py` -> outputs/final/forecast_backtest.csv, runs validate_submission.py.
- Organiser tools run via `python -I starter_package_v1/{validate_submission,score,make_templates}.py` (outputs elsewhere).
- LightGBM on macOS needed `brew install libomp` (done).

## Model
Target = imbalance - spot(target) ("spread"); p10/p50/p90 LightGBM quantile, multiclass direction (down/none/up),
2 binary spike classifiers (+-50 vs spot). 3 seeds averaged, early-stopped rounds on a time-ordered inner split (last 14 d
with 10 h embargo), refit on all; p10/p90 shifted by conformal offsets from the inner holdout (coverage 0.64 -> ~0.80).
Post: sort quantiles, renormalise direction, scale spikes so high+low <= 1. top_drivers = grouped SHAP (pred_contrib) of p50.
data_cutoff_utc = max first_usable among cells in the window (usually == origin).

## Findings (validation 7 Sep–4 Oct, baseline: MAE 66.20, pinball 24.18, cov 0.68, spike 0.1132, dir 0.4509)
- Baseline reproduced exactly via src/baseline.py.
- Current model ~ MAE 43.6, pinball 12.34, cov 0.805, spike 0.0965, dir 0.415.
- Spread autocorrelation ~0 beyond 1 h; constant "spot-12" gives MAE 43.7; oracle-direction gives 35.4 -> skill comes from
  day-ahead structure (spot, cons/wind/solar forecast changes) and direction, not recency. Error is flat across horizon.
- Did NOT help: recency weighting (halflife 30/60/120 d), level target (worse MAE), bigger trees. Autumn has more high spikes
  than summer training (base-rate shift) -> p_spike_high under-predicted at the low end.

## LUMI (deferred — user does not have access sorted yet)
Local training takes ~20 s, LUMI is optional. When the user is ready: inspect `lumi-workspaces`, ask for project ID; write
scripts/train_cpu.sbatch (small partition, LightGBM); give rsync commands excluding .git/.venv/outputs.

## Status
Done: availability+tests, baseline reproduction, features, models, validation, final run (validator passes, 0 errors),
exports, README/SOURCES/REPORT, scripts/train_cpu.sbatch (untested, account placeholder).
Left: LUMI access (user deferred) (alerts feature was removed at user request), commit when user asks.

## Improvement ideas (user said keep in mind; ranked)
1. Rolling-window validation (several weeks, expanding train) to trust comparisons. 2. Better direction forecasting
(oracle direction would cut MAE ~44 -> ~35). 3. Direction-aware price model (up/down regime prices mixed by P(direction)).
4. Spike probability calibration (base-rate shift). 5. Open-Meteo Single Runs only with publication delay (risky). 6. Jury 20 pts:
slides/demo story matter as much as spike score.

## Viewer
`scripts/show_origin.py <ISO origin>` (terminal) and `app/app.py` (Streamlit, `uv run --group app streamlit run app/app.py`)
read outputs/validation/backtest_vs_actual.csv and outputs/final/*.csv (no spot values). Smoke-tested with streamlit AppTest.

## React viewer (preferred over Streamlit)
web/ = Vite + React + Recharts. `uv run scripts/export_web_data.py` writes web/public/data/{validation,final}.json
(gitignored, no spot values); `cd web && npm install && npm run dev` -> http://localhost:5173. Features: set switch,
date/hour picker with +-1 h, summary text, KPIs, p10-p90 chart vs actual, probabilities, drivers,
daily MAE in hindsight. Builds and serves OK; NOT yet visually checked in a browser.
