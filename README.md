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

## Pick what you want to do
| I want to... | Go to | You need |
|---|---|---|
| **Just look at the forecasts on the website** | Part A (5 minutes) | Node.js, git, and the folder `web/public/data/` from the model owner |
| **Train the model myself and reproduce the results** | Part B (about 15 minutes of work) | git, uv, the organisers' data package; on a Mac also `brew install libomp` |

The repo contains **no data and no trained model**: the data is licensed (Nord Pool spot prices are hackathon-only and must never be committed or
shared), and training only takes about a minute on a normal laptop (CPU, no GPU needed). That is why Part B trains the model on your own computer.

## Part A: look at the forecasts on the website
Works the same on macOS, Linux and Windows. Type the commands in a terminal (on Windows: PowerShell or the terminal inside VS Code).

**1. Install Node.js** (version 20 or newer) from https://nodejs.org if `node --version` does not print a number. This also installs `npm`.

**2. Get the code**
```bash
git clone https://github.com/otsosaarinen/since-ai-turku-energia.git
cd since-ai-turku-energia
```

**3. Add the forecast files.** Ask the model owner for the folder `web/public/data/` (about 75 MB) and copy it into the repo so the files end up at
`web/public/data/validation.json`, `web/public/data/final.json` and `web/public/data/variants/`. They are not in git, because the
forecasts come from licensed data. Without `variants/` the website works, but the three input switches say "not computed yet".

**4. Install and start the website** (the first command downloads the website's libraries, only needed once and takes about a minute)
```bash
cd web
npm install
npm run dev
```
**5. Open http://localhost:5173** in your browser. Stop the website with Ctrl+C in the terminal.

Next time you only need `cd web` and `npm run dev`. On macOS and Linux, `./scripts/start_web.sh` from the repo folder does the same
(and on the model owner's computer it also rebuilds the website's data from `outputs/` first). It does not work on Windows.

Other website commands (run inside the `web/` folder): `npm test` (19 tests), `npm run typecheck` (TypeScript check), `npm run build` (production build).
What the page shows is described under "What the website shows" further down.

## Part B: train the model yourself
Requirements: macOS or Linux, [git](https://git-scm.com), [uv](https://docs.astral.sh/uv/) (installs Python for you; install with
`curl -LsSf https://astral.sh/uv/install.sh | sh`). On macOS also run `brew install libomp` once (LightGBM needs OpenMP).
Node.js is only needed if you also want the website.

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
uv run pytest -q                       # 35 tests: availability filter, leakage checks, input groups, harness server (about 20 s)
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

## What the website shows
```bash
uv run scripts/show_origin.py 2026-09-20T09:00   # (optional) one validation origin in the terminal instead of the website (UTC)
```
The website (`web/`, React + TypeScript + Vite + Recharts) is one screen without scrolling on a laptop screen; on a phone or narrow window it becomes one scrolling column: method boxes and chart first, the time controls under the chart, the summary below, and the period buttons and input switches in a column above the chart (the switches behind a "Forecast inputs" button). It follows the Turku Energia graphic guidelines (white page, orange
as the accent colour, blue and grey structure with WCAG AA contrast, bold condensed capital headlines, plain wording), uses Finnish time and
dd/mm/yyyy, and keeps its text short (no "i" tooltips; the chart legend explains the lines). The team name ("Perjantain kevätrulla") is under the title. The address shows the chosen tab: `/?method=harness` for the Harness prediction, plain `/` for the Machine-learning model (the default). What is on the screen, top to bottom:
- **Period buttons:** the validation month (with real prices) or the test forecast (without), two equal-width buttons at the top of the left column, above the input switches. Shown only for the "Machine-learning model" box; hidden on the Harness prediction page.
- **Two method boxes:** **Machine-learning model** (this repo's LightGBM forecasts) and **Harness prediction** (a second method whose code is in `harness/`, see
  "Harness prediction" below; its forecasts are not connected to the chart yet). The highlighted box decides what the chart shows. To connect it, add forecasts as
  `web/public/data/harness_validation.json` and `harness_final.json` in the same format as `validation.json` / `final.json` (`{name, hasActuals, cols, rows}`, see
  `src/exports.py` `web_payload`); until then its box shows a "not connected yet" message. The harness makes live forecasts, not a backtest, so a converter and a decision on
  what to show are still needed.
- **Summary strip:** one plain sentence (does the grid need more or less power) and three numbers (chance of a high and of a low price spike
  and, when real prices are known, the average error). The method boxes show only their titles; a one-line note under them says what the machine-learning forecast is. Kept short on purpose: the page was found cluttered, so everything else was cut. All cards are plain white.
- **Chart (in the middle, as big as possible):** forecast, likely range (blue), real price (red: solid = already published when the forecast was made, dashed = published after it; the legend and hover text say which), the forecast made 3 h earlier (grey) and a
  "Forecast made" line. The price axis is fixed (-50 to 350 EUR/MWh, from the data: the forecast line's 99.9th percentile and the likely range's 99th) so its numbers never move while time moves or plays;
  rare larger values run off the top and show in the hover tooltip. Above it: 1 h / 1 day steps that glide smoothly, a date list, a bar over the whole period, a **Play** button (speeds 1x, 3x,
  10x forecast hours per second; stops at the end). The **input switches** are stacked in a column to the left of the chart.
- **Input switches (Machine-learning model only):** turn Fingrid's day-ahead **solar**, **wind** and **consumption** forecasts on or off. The page cannot
  re-run the model, so each of the 8 combinations is a separately trained model computed beforehand with `uv run scripts/run_variants.py`
  (7 extra variants, about 12 minutes, files in `web/public/data/variants/`). A label shows the average error of the chosen variant.
  Residual-load features combine all three forecasts, so they are removed whenever any switch is off. Real cloud or sunlight data is not in the model.

**Where the website's data comes from.** `web/public/data/` (git-ignored: forecasts and real imbalance prices, no spot prices) is created by
`uv run scripts/export_web_data.py` from `outputs/` on the model owner's computer (`start_web.sh` calls it automatically), or copied from them
(Part A, step 3). `app/app.py` is an older, optional Streamlit viewer (`uv run --group app streamlit run app/app.py`).

## Put the website online for a demo (optional)
The website only reads the ready-made JSON files in `web/public/data/`, so it is a plain static site: no server, Python or model is needed online.
```bash
cd web
npm install
npm run build                  # type-checks, then writes the site (including the data files) to web/dist/
npx vercel login               # once
npx vercel deploy dist         # prints a .vercel.app link; add --prod for a public link
```
A plain preview link is only visible to people logged in to your Vercel account; turn off "Vercel Authentication" in the project's Deployment Protection
settings to share it. **Licence:** the forecasts are built on the Nord Pool spot data, which is hackathon-only. Keep the link unlisted, ask the organisers
before keeping it public, and delete the Vercel project after the event (`npx vercel remove <project-name>`). Local alternative without uploading anything:
`npm run dev -- --host` and share a tunnel such as `npx cloudflared tunnel --url http://localhost:5173`. Not tested end to end.

## Harness prediction (second method, in `harness/`)
`harness/` holds code copied from https://github.com/rogue-agent/livelectroray (commit `b44314d`, reviewed read-only; see `harness/README.md`). It lets an AI model run Python
and fetch live data, so treat it as untrusted: its `run_python` tool runs model-written code with your full user access. It uses this project's uv environment, so there is only
one uv project: `uv sync --group harness` installs its packages (openai, scipy, statsmodels). With a local model server such as the Llama app on port 9931 (context 16k or more):
```bash
HARNESS_PROVIDER=llamacpp LLAMACPP_BASE_URL=http://localhost:9931/v1 \
  uv run --group harness python harness/harness.py -m "ggml-org/gemma-4-E4B-it-GGUF:Q8_0" -q "what is 17*23? use python"
```
**Start and watch runs from the website.** Start the local control server in one terminal and the website in another:
```bash
./scripts/start_harness.sh     # control server on 127.0.0.1:8765; needs the local model server (Llama app, port 9931)
./scripts/start_web.sh         # the website; pick "Harness prediction", choose a model, press Start run
```
The panel has a short intro and two fixed forecast choices (imbalance price next 12 h; day-ahead price next 12 h) with a one-line description under the buttons. A **Settings** button opens a pop-up with the model picker (only the small gemma-4 E4B model; the server filters the Llama app's model list; `HARNESS_MODEL_FILTER=E4B,12B ./scripts/start_harness.sh` offers more) and the API keys. The elapsed time / "Done in …" sits next to the "Progress." heading; the prompt text cannot be edited on the page and lives in `harness/server.py` (`PRESETS`), which accepts only a preset name,
shows the run live as a short list of steps (one per call to the model, named by what it did, e.g. "Step 2: Fetching nordpool_price"; small compact text, finished steps have a check mark, the current one a spinner, the list scrolls inside its own box, a failed fetch shows its error under the step, and the model's reasoning is behind a "Reasoning" fold-out under the step, shown in full, from the `[think]` progress line) and, when finished, the answer (the table is found even if the model forgets the code fence) as a chart (orange forecast line, blue low-to-high range) in Finnish time; the table is shown instead when the answer has too few points for a chart. `[turn k/10]` counts calls to the model; 10 is only the maximum, a run ends when the model decides to answer. The server tells the model the current UTC time and to use ISO timestamps (small models otherwise send words like "5 hours ago" to the data sources). It works only on your own computer with the Vite dev server
(the proxy `/harness-api` in `web/vite.config.ts`); on a hosted copy (Vercel) it only explains how to start the server. One run at a time, stopped after 20 minutes, **Stop** ends it.
The server (`harness/server.py`, written for this repo) listens on 127.0.0.1 only and refuses any request whose Host or Origin is not localhost, because a run executes model-written Python.
On the command line the same progress lines appear with `--progress` (added to `harness/harness.py`).
Fetched data is saved to `harness/reports/data/` (git-ignored); the model sees a short preview and the file path and is told to load the file in its Python code instead of pasting data into it (long pasted JSON made the small model write broken code). Tool calls that arrive cut off get their own retry budget of 4 and do not count towards the 10 turns.

**API keys:** the Settings pop-up shows an input field for each missing key (Fingrid, ENTSO-E; OpenRouter only for the hosted provider) and saves it to `harness/key.txt` (git-ignored, 0600) without showing it again. On the command line the harness asks for missing keys on startup (Enter skips) and saves them there. Without the Fingrid key the `fingrid_*` sources fail. Example question that uses it (run from the repo folder):
```bash
HARNESS_PROVIDER=llamacpp LLAMACPP_BASE_URL=http://localhost:9931/v1 \
  uv run --group harness python harness/harness.py -m "ggml-org/gemma-4-E4B-it-GGUF:Q8_0" -q "predict the Finnish imbalance price every 2 hours for the next 12 hours"
```
Each answer's csv block (fenced or a plain table) is written automatically to `harness/reports/prediction.csv` and `harness/reports/prediction.md` (human-readable table); `report.py answer.txt` does the same from a saved answer. It makes live forecasts (next 24 h / 7 days)
and is **not a backtest and not part of the submission file**, so its output does not fit the website's chart as it is. First tests (7 Nov, gemma-4 E4B Q8, 32k context, Llama app):
it works end to end (about 20 s for a simple question, 2-6 min with data) but a small local model gave weak forecasts, see `EXPERIMENTS.md` section 8. Progress lines go to stderr (`--progress`, or on in the website panel). Plain `uv sync`
removes the harness packages again; run `uv sync --group harness` to get them back. Keys live in `harness/key.txt` and reports in `harness/reports/` (both git-ignored).

## Layout
- `src/availability.py` availability filter (fast index, same result as the organiser's `rows_available_at`)
- `src/features.py` features per (origin, step) and the input groups the viewer can switch off | `src/train.py`, `src/predict.py` models |
  `src/evaluate.py` validator and scorer wrappers | `src/exports.py` viewer tables | `src/baseline.py` organiser baseline
- `scripts/` `run_validation.py`, `run_rolling.py`, `run_final.py`, `run_variants.py`, `exp_postproc.py`, `export_web_data.py`, `start_web.sh`, `start_harness.sh`, `show_origin.py`,
  `train_cpu.sbatch` (LUMI Slurm job for the final run; untested, LUMI is optional because local training takes about a minute)
- `harness/` the harness code (second method) and `server.py`, the control server behind the website panel | `web/` React viewer (`web/src/design-system/` = Turku Energia design components) | `tests/` Python tests | `configs/default.yaml` all model settings
