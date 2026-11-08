# Imbalance price forecast, 10 h ahead

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![LightGBM](https://img.shields.io/badge/LightGBM-models-2E8B57)](https://lightgbm.readthedocs.io)

**Team Perjantain kevätrulla** · Since AI 2026 · Turku Energia challenge

We forecast the Finnish imbalance price for the next 10 hours (40 quarter-hours), every full hour: a most likely price
(P50), a likely range (P10 to P90), the direction of the balancing need (up, down, none) and the chance of an
exceptional price (more than 50 EUR/MWh above or below the day-ahead price). A web viewer lets you step through every
forecast and replay the past month as if it were live. Only data that was available at forecast time is used.

**Live demo: https://imbalance-forecast-demo.vercel.app** (press **How to use** in the top right corner).

## For the judges: what is where

| Required in the briefing | Where it is |
|---|---|
| Forecast file `forecast_backtest.csv` (673 origins x 40 quarter-hours = 26,920 rows) | In the submission zip (root). Rebuild it with `uv run scripts/run_final.py`, see [Train the model](#train-the-model). Not in git because the repo is public and data files are never committed. |
| Source code and start-up instructions | This repository. Start-up: [Quick start](#quick-start) below. |
| Short evaluation report: reasoning chain, factors, validation metrics | **[REPORT.md](REPORT.md)**. Every experiment with numbers: [EXPERIMENTS.md](EXPERIMENTS.md). |
| List of data sources, services, ready-made models, software and their licences | **[SOURCES.md](SOURCES.md)** |
| 5-8 slides and the demo video (max 5 min) | Uploaded separately in the Since AI app (not part of the repository). |

**Result on the validation month** (7 Sep to 4 Oct 2026, the organisers' `score.py`, baseline versus our model):

| Metric | Baseline | Our model |
|---|---|---|
| Accuracy: average error of P50 (EUR/MWh) | 66.20 | **43.21** |
| Calibration: mean pinball loss of P10/P90 | 24.18 | **12.42** |
| Exceptional prices: Brier score | 0.1132 | **0.0967** |
| Direction: Brier score | 0.4509 | **0.4121** |

The test month (5 Oct to 1 Nov) cannot be scored locally because its real prices are held by the organisers.

### How we keep to the availability rule (no data from the future)

- `backend/src/availability.py` is the only way features get data: at forecast origin `t` a row is usable only if
  `first_usable_origin_utc <= t`. Lags, rolling values and "latest" values are computed after that filter.
- Training uses only 1 Jun to 4 Oct 2026. Test-period rows and labels are never used for training.
- Tests (`backend/tests/`) prove the filter matches the organisers' `rows_available_at`, and that features stay
  bit-identical when every not-yet-usable row is deleted or overwritten with garbage.

### What the web viewer shows (Level 2)

- **Next 10 hours:** the forecast, its likely range, the real price once known, and the forecast made 3 hours earlier.
- **Alerts and suggestions:** the chance of a high or low price spike, with the time window and a suggested action
  (for example to review the production plan) when the risk is high.
- **Past performance:** how the forecast did before the chosen time (last 24 h, last 7 days, since the start).
- **Moving time:** any forecast of the period can be selected with the slider, date list or 1 h / 1 day steps, or played forward.
- **Input switches:** turn the solar, wind or consumption forecast off to see a model trained without it.
- The optional **Harness** (a live AI demo) is a separate tab for local use and is not part of the scored forecast.
  The hosted demo hides it.

## Quick start

You need [git](https://git-scm.com), [Node.js](https://nodejs.org) 20+ and [uv](https://docs.astral.sh/uv/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`). On a Mac also run `brew install libomp` once.

```bash
git clone https://github.com/otsosaarinen/since-ai-turku-energia.git
cd since-ai-turku-energia
./dev.sh --no-harness
```

Open http://localhost:5173. Stop with Ctrl+C. `./dev.sh` turns your model results into the website's data files
(if you have run the model, see below) and starts the website. Without `--no-harness` it also starts the optional Harness server.

The repo has **no data**: it is licensed and must never be committed. Without the forecast files in
`frontend/public/data/` the page says the data is missing. Make them by training the model (next section)
or use the live demo above.

## Train the model

Takes about two minutes. Download `starter_package_v1.zip` from the challenge page, then:

```bash
cd backend
uv sync
unzip ~/Downloads/starter_package_v1.zip
mkdir -p data
cp starter_package_v1/data/{inputs.parquet,spot_nordpool.csv,actuals_validation.csv} data/
uv run python -c "from src.baseline import *; run_validation_baseline('starter_package_v1','data','outputs/baseline/validation')"
uv run scripts/run_validation.py      # train before 7 Sep, score 7 Sep - 4 Oct
uv run scripts/run_final.py           # train up to 4 Oct, write outputs/final/forecast_backtest.csv
uv run scripts/export_web_data.py     # data files for the website
```

Expected: validation average error 43.21; `run_final.py` ends with `Errors: 0` (the organisers' format validator passes).
Run the tests with `uv run pytest -q` (164 backend tests; the frontend has 176: `cd frontend && npx vitest run`).
All model settings are in `backend/configs/default.yaml`.

## Folders

```
frontend/   Next.js website            see frontend/README.md
backend/    Python
  src/        availability filter, features, models, scoring
  scripts/    train, validate, export
  tests/      Python tests
  configs/    model settings
  harness/    optional AI demo         see backend/harness/README.md
dev.sh      start everything
REPORT.md · EXPERIMENTS.md · SOURCES.md    the documents above
```

Checks run on every push (`.github/workflows/ci.yml`): lint, types, tests and a build for the frontend, tests
for the backend. They need no licensed data.

## Settings

One settings file for the whole project: `.env` in the repo root (git-ignored). Create it with
`cp .env.example .env`. You do not need it for the model or the website.

| Setting | Meaning |
|---|---|
| `FINGRID_API_KEY`, `ENTSOE_API_KEY` | Keys for the optional Harness only. |
| `NEXT_PUBLIC_HIDE_HARNESS=true` | Hides the Harness completely (used for the hosted demo). |
| `NEXT_PUBLIC_DATA_BASE_URL` | Where the website loads the forecast files from. Default: `/data`. |

`NEXT_PUBLIC_` settings are baked in when the site is built, so restart or rebuild after changing them.

## Host the website on Vercel

1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend` (framework Next.js, Node 22).
2. Add the variable `NEXT_PUBLIC_HIDE_HARNESS` = `true`, then deploy.
3. The forecast files are not in git, so the site says the data is missing until you host them. Create a public
   **Vercel Blob** store (Storage tab) and upload only the 17 website files (`validation.json`, `final.json` and
   the 15 files in `variants/`, including `variants/index.json`) with
   `npx vercel blob put <file> --access public --pathname <name> --force`.
4. Set `NEXT_PUBLIC_DATA_BASE_URL` to the store's address (`https://<store-id>.public.blob.vercel-storage.com`,
   no trailing slash) and redeploy.

Never upload `backend/data/` (it holds the Nord Pool spot prices and `actuals_validation.csv`, which has a `spot_price`
column) or `backend/outputs/`. The 17 website files contain no spot prices. The briefing says the spot data must
not be shared or published and must be deleted after the event: delete the Blob store as well.
