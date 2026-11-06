# CLAUDE.md — Turku Energia imbalance price forecast (Since AI 2026)

Deadline: Sun 8 Nov 2026, 10:00. Forecast Finnish `fi_imbalance_price` 40 quarter-hours (10 h) ahead from every full-hour origin;
backtest 5 Oct–1 Nov 2026 = 673 origins x 40 = 26,920 rows -> `forecast_backtest.csv`. Data is UTC; the web viewer shows Finnish time
and dd/mm/yyyy. The user owns the model work; teammates build the frontend.

**Where facts live (do not duplicate them here — they drift):**
README.md = setup and commands, current headline results. REPORT.md = reasoning, validation vs test, how the model is trained and
why, score tables. EXPERIMENTS.md = every test with numbers and decisions. SOURCES.md = data, services, licences.
Config (periods, seeds, LightGBM settings) = configs/default.yaml.

## HARD RULES (violation = score 0 / code audited)
- At origin t use a row only if `first_usable_origin_utc <= t`. Build every feature from `AvailabilityIndex.at(origin)`
  (src/availability.py) ONLY; compute lags/rolling/latest AFTER filtering. Never touch the unfiltered table.
- Train only on 1 Jun–4 Oct 2026. Never use test-period (after 4 Oct) rows or labels. Validation: train only with labels usable at the
  first validation origin (2026-09-06T21:00Z). Labels go through `AvailabilityIndex.labels(..., known_at=cutoff)`.
  A training origin o is usable at cut-off c only if o + 11 h <= c (all 40 labels published).
- Target quarter-hours' own actuals are never features. aFRR series are sparse: no row = no activation; never forward-fill.
- The briefing PDF (~/Downloads, slides 11 and 25) is the authority: extra open/paid data is allowed if sources and licences are
  listed, but test-period data is never used for training. No Open-Meteo Historical Forecast API.
- `data/spot_nordpool.csv` (Nord Pool) is hackathon-only: never print its rows, commit, share, or export spot values. `data/`,
  `outputs/`, `starter_package_v1/`, `*.csv`, `*.parquet` and model files are gitignored. Delete the data after the event.
  The GitHub repo (otsosaarinen/since-ai-turku-energia) is PUBLIC: check `git status` and never add data or outputs.
- `starter_package_v1/` is read-only reference. Write all code outside it.
- Do not commit or push unless the user asks.

## Commands (uv project: `uv sync`, then `uv run ...`)
- `uv run pytest -q` (21 tests) and `cd web && npx vitest run` (1 test).
- `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` -> validation month, scored vs baseline, in outputs/X/.
- `uv run scripts/run_rolling.py [--tag X] [--ref TAG] [--set key=value ...]` -> 8 weekly windows; judge model changes here.
- `uv run scripts/run_final.py` -> outputs/final/forecast_backtest.csv and runs the organiser validator.
- Organiser tools: `uv run python -I starter_package_v1/{validate_submission,score,make_templates}.py`.
- Viewer: `./scripts/start_web.sh` (http://localhost:5173). Streamlit `app/` is optional/older.
- LightGBM on macOS needed `brew install libomp` (done).

## Status (7 Nov 2026)
- Submission `outputs/final/forecast_backtest.csv` exists and passes the validator. Model: six LightGBM models predicting
  imbalance minus spot (see REPORT.md); it is near the ceiling of this data (EXPERIMENTS.md).
- Git: remote `origin` exists and the first two commits are pushed; later local commits/edits are pushed only when the user says so.
- LUMI: not set up (no access yet; training takes about a minute locally). `scripts/train_cpu.sbatch` is untested with a placeholder
  project ID. If asked: `lumi-workspaces` for the project ID, then give rsync commands excluding .git/.venv/outputs.

## Next ideas (none started)
Slides (5-8) and demo script (jury part is 20 points); direction-aware price model; spike probability calibration;
more direction features. Extra pre-June history was judged not worth the risk (EXPERIMENTS.md).
