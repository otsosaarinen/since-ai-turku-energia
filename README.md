# Imbalance price forecast, 10 h ahead

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![LightGBM](https://img.shields.io/badge/LightGBM-models-2E8B57)](https://lightgbm.readthedocs.io)

Team **Perjantain kevätrulla**, Since AI 2026, Turku Energia challenge.

Forecasts the Finnish imbalance price for the next 10 hours (40 quarter-hours), every full hour:
a most likely price, a likely range, the direction (up or down) and the chance of a price spike.
A web viewer lets you step through every forecast. Only data available at forecast time is used.

**Result** (validation month, baseline vs our model): average error **66.20 vs 43.21** EUR/MWh.
Details: [REPORT.md](REPORT.md) (reasoning and scores), [EXPERIMENTS.md](EXPERIMENTS.md) (every test),
[SOURCES.md](SOURCES.md) (data and licences).

## Quick start

You need [git](https://git-scm.com), [Node.js](https://nodejs.org) 20+ and [uv](https://docs.astral.sh/uv/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`). On a Mac also run `brew install libomp` once.

```bash
git clone https://github.com/otsosaarinen/since-ai-turku-energia.git
cd since-ai-turku-energia
./dev.sh
```

Open http://localhost:5173. Stop everything with Ctrl+C. `./dev.sh` does three things:

1. Turns your model results into the website's data files (if you have run the model, see below).
2. Starts the optional Harness server (an AI demo). Skip it with `./dev.sh --no-harness`.
3. Starts the website.

The repo has **no data**: it is licensed and must never be committed. Without the forecast files in
`frontend/public/data/` the page says the data is missing. Make them by training the model (next section)
or ask the model owner for that folder.

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

Expected: validation average error 43.21; `run_final.py` ends with `Errors: 0`. Run the tests with `uv run pytest -q`.
All settings are in `backend/configs/default.yaml`.

## Settings

One settings file for the whole project: `.env` in the repo root (git-ignored). Create it with
`cp .env.example .env`.

| Setting | Meaning |
|---|---|
| `FINGRID_API_KEY`, `ENTSOE_API_KEY` | Keys for the Harness. The website's Settings box can save them too. |
| `NEXT_PUBLIC_HIDE_HARNESS=true` | Hides the Harness completely (use this for the hosted demo). |
| `NEXT_PUBLIC_DATA_BASE_URL` | Where the website loads the forecast files from. Default: `/data`. |

`NEXT_PUBLIC_` settings are baked in when the site is built, so rebuild after changing them.

## Host the website on Vercel

1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend` (framework Next.js, Node 22).
2. Add the variable `NEXT_PUBLIC_HIDE_HARNESS` = `true`, then deploy.
3. The forecast files are not in git, so the site says the data is missing until you host them. Create a public
   **Vercel Blob** store (Storage tab) and upload only the 16 website files (`validation.json`, `final.json` and
   the files in `variants/`) with `npx vercel blob put <file> --access public --pathname <name> --force`.
4. Set `NEXT_PUBLIC_DATA_BASE_URL` to the store's address (`https://<store-id>.public.blob.vercel-storage.com`,
   no trailing slash) and redeploy.

Never upload `backend/data/` (it holds the Nord Pool spot prices and `actuals_validation.csv`, which has a `spot_price`
column) or `backend/outputs/`. The 16 website files contain no spot prices. The briefing says the spot data must
not be shared or published and must be deleted after the event: delete the Blob store as well.

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
```

Checks run on every push (`.github/workflows/ci.yml`): lint, types, tests and a build for the frontend, tests
for the backend. They need no licensed data.
