# CLAUDE.md — Turku Energia imbalance price forecast (Since AI 2026)

Forecast the Finnish imbalance price (`fi_imbalance_price`) 40 quarter-hours (10 h) ahead from every full-hour origin. Backtest 5 Oct–1 Nov 2026 =
673 origins x 40 = 26,920 rows -> `forecast_backtest.csv`. Deadline: Sun 8 Nov 2026, 10:00. Data is UTC; the web viewer shows Finnish time and dd/mm/yyyy.

**Where facts live (do not duplicate numbers here, they drift):** README.md = setup, commands, viewer, headline results. REPORT.md = reasoning chain,
validation vs test, how the model is trained and why, score tables, factors affecting the forecast. EXPERIMENTS.md = every test with numbers and
decisions. SOURCES.md = data, services, components, licences. configs/default.yaml = periods, seeds, LightGBM settings.

## HARD RULES (violation = score 0 / code is audited)
- At origin t use a row only if `first_usable_origin_utc <= t`. Build every feature from `AvailabilityIndex.at(origin)` (src/availability.py) ONLY;
  compute lags/rolling/latest AFTER filtering. Never touch the unfiltered table.
- Train only on 1 Jun–4 Oct 2026. Never use test-period (after 4 Oct) rows or labels. Validation: train only with labels usable at the first
  validation origin (2026-09-06T21:00Z); labels go through `AvailabilityIndex.labels(..., known_at=cutoff)`. A training origin o is usable at
  cut-off c only if o + 11 h <= c (all 40 labels published).
- Target quarter-hours' own actuals are never features. aFRR series are sparse: no row = no activation; never forward-fill.
- The briefing PDF (~/Downloads/Turku_Energia_Imbalance_Price_Challenge_Briefing.pdf, slides 11 and 25) is the authority: other open/paid data is
  allowed if sources and licences are listed, but test-period data is never used for training. No Open-Meteo Historical Forecast API.
- `data/spot_nordpool.csv` (Nord Pool) is hackathon-only: never print its rows, commit, share or export spot values. `data/`, `outputs/`,
  `starter_package_v1/`, `*.csv`, `*.parquet`, `*.pkl`, `*.zip`, `.env`/`.secrets/`, `web/public/data/` are git-ignored. Delete the data after the event.
  The GitHub repo (otsosaarinen/since-ai-turku-energia) is PUBLIC: check `git status` before any commit; never add data, outputs or keys.
- `starter_package_v1/` is read-only reference. Write all code outside it. Never modify files in ~/Downloads.
- Do not commit or push unless the user asks. Do not write files when the user says to keep the repo clean.

## Working with the user (Otso)
- Owns the model work; teammates build the frontend; a friend may want to run the website. Not an ML or electricity-market expert: explain in plain
  language, say what he must run himself, give exact commands, and say honestly when something is a guess or not verified (e.g. "not seen rendered").
- Uses Safari on macOS and sends screenshots; there is no headless browser here, so web changes are tested with Vitest/jsdom only.
- Short answers; state what was done and what is uncommitted. Commits/pushes only on request (he pushes himself or says so).

## Commands (uv project: `uv sync`, then `uv run ...`; macOS needed `brew install libomp`, done)
- `uv run pytest -q` (35 tests) and `cd web && npx vitest run` (18 tests).
- `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` -> validation month, scored vs the organisers' baseline, outputs/X/.
- `uv run scripts/run_rolling.py [--tag X] [--ref TAG] [--set key=value ...]` -> 8 weekly windows; judge model changes here.
- `uv run scripts/run_final.py` -> outputs/final/forecast_backtest.csv and runs the organiser validator.
- `uv run scripts/exp_postproc.py` -> post-processing experiments on the 8 windows (section 7 of EXPERIMENTS.md).
- `uv run scripts/run_variants.py` -> the 7 model variants behind the viewer's input switches (about 12 min).
- Organiser tools: `uv run python -I starter_package_v1/{validate_submission,score,make_templates}.py`.
- Harness panel server: `./scripts/start_harness.sh` (needs the Llama app). Viewer: `./scripts/start_web.sh` (http://localhost:5173). `scripts/export_web_data.py` writes web/public/data/{validation,final}.json from outputs/.

## Model (details in REPORT.md)
Target = imbalance minus spot of the target quarter-hour. Six LightGBM models: quantile p10/p50/p90, 3-class direction, two spike models (+-50 EUR/MWh
vs spot). 8 leaves, extra-trees, 6 seeds, rounds from a time-ordered inner split (14 d, 10 h embargo), p10/p90 shifted by conformal offsets.
`model.drop_features` in the config leaves features out (used for the viewer switches). Near the ceiling of this data (EXPERIMENTS.md).

## Web viewer (web/, React + TypeScript + Vite + Recharts + Tailwind 4; tests Vitest + jsdom)
- TypeScript (strict): `src/App.tsx`, `src/types.ts` (forecast file shapes), `src/main.tsx`, tests in `web/test/*.tsx`. Check types with `cd web && npm run typecheck`; `npm run build` type-checks first. Keep new code typed (no `any`).
- Layout: one screen, no scrolling on large screens (lg = 1024 px and up). Below that it is a single scrolling column in this order: title and period (period buttons only when the Machine-learning box is active; hidden for Harness), the two method boxes (compact, one short line each), the chart (20 rem tall) with the time controls under it, then the note and the summary strip last (text not clamped); pitfall: `flex-1` on a column child overrides its height and collapses the chart, so the chart box uses `lg:flex-1` only; the input switches sit behind a "Forecast inputs" button that opens a pop-up panel (`inputsOpen` state). Responsive classes use Tailwind `lg:`; not seen on a real phone (no browser here), only the code and tests were checked; wave background (light-blue wave + orange hill); title row, period buttons, two method boxes,
  a fixed-height summary strip (one sentence, drivers, three chips: high spike, low spike, average error; cut down on purpose, do not add more text), then the chart centred and as large as possible with time controls above it
  and the input switches stacked vertically in a narrow column left of the chart (the user asked for this; no other left column). Do not define components inside `App` (it remounts the controls; a test guards this).
- Methods: boxes "Machine-learning model" (was "Current model") and "Harness prediction" (METHODS in App.tsx). Harness has no forecast files yet: it reads
  web/public/data/harness_{validation,final}.json (same format as validation.json) and shows "not connected yet" until they exist.
- Input switches (TOGGLES in App.tsx, groups in src/features.py TOGGLE_GROUPS): 8 precomputed variants in web/public/data/variants/
  {validation,final}_<key>.json + index.json (key digits = solar, wind, consumption; 111 = normal model). Residual-load features are dropped whenever any
  group is off. The page keeps the old chart on screen and the chosen hour while a variant loads (no blink).
- Fixed price axis: `yAxis` in App.tsx is computed once per loaded file (percentiles, rounded to 50 EUR/MWh; -50..350 for the current data; covers the 99.9th percentile of the forecast line so forecasts around 300 fit) and
  `allowDataOverflow` clips rare spikes; the user wants the axis numbers to stay put while playing (a test guards this).
- Smooth time: position is fractional (`fpos`); the numeric time axis slides and neighbouring forecasts (and the forecasts made 3 h earlier) are blended;
  1 h / 1 day buttons glide; Play advances 1/3/10 forecast hours per second and stops at the end. Tests mock ResponsiveContainer so the chart renders.
- Brand rules ("Graafinen ohjeisto", ~/Downloads/Graafinen ohjeisto.pdf; web pp. 12-14, 48-49): white base, orange as accent (visible: hill, active
  boxes/buttons, switches, slider), blue/grey structure with AA contrast. Orange surfaces with white text use #B46000 (AA); bright #F59B00 only as
  decoration; forecast line deepened orange #C96A00; real prices red (design-system destructive); likely range blue #46BEDC; earlier forecast grey.
  Headlines: Fira Sans Extra Condensed, bold capitals ending with a full stop. Never text on plain orange, never black on orange. Do NOT build a logo
  from an orange bar + text (forbidden); ask the user for the official digital logo file if a logo is wanted.
- Wording: plain language (no "p50", "in band"); only two `Info` tooltips (period, key numbers) (the user found many annoying); text areas have fixed heights so changing
  numbers never shift the chart. Design components were copied from a Lovable template (~/Downloads/d489a847-...; only the design system was used).

## Harness (harness/, copied from another repo)
`harness/` = copy of https://github.com/rogue-agent/livelectroray at b44314d (brand-new anonymous repo, no licence file, reviewed read-only: no malware seen, but its `run_python`
tool executes model-written code with full user access; prompt injection from fetched web data is the main risk). Run from `harness/` with this project's uv env
(`uv run --group harness python harness.py ...`, group `harness` in pyproject.toml). `harness/key.txt` and `harness/reports/` are git-ignored. Do not edit its code without noting it
in harness/README.md. It is a live 24 h / 7 d analyst, not a backtest: its csv (horizon,time,area,metric,value,unit,low,high,confidence,drivers) cannot fill the website's harness JSON
without a converter and a decision on what to show. The Llama app (localhost:9931, OpenAI-style API) needs context >= 16k for it; the harness picks the FIRST listed model if `-m`
is missing (that is the tiny Qwen). Website panel (web/src/HarnessPanel.tsx, shown when the harness box has no forecast JSON): talks to harness/server.py (our own control server, 127.0.0.1:8765, started with
scripts/start_harness.sh) through the Vite proxy `/harness-api`; model list from the Llama app filtered to E4B (env HARNESS_MODEL_FILTER), two fixed presets (prompts live in harness/server.py PRESETS; the browser sends only a preset id, free text is refused, no prompt box on the page), live progress as a step list (with the model's reasoning per step, from `[think]` lines logged by harness.py; shown in full; confirmed working by the user on a real run with the local gemma model, 7 Nov) built by parseSteps() from the harness.py `--progress` lines (our small edit; done steps grey, active step spinner), answer table (the progress list scrolls in its own box, max 45% of the column once an answer exists; fetched data is saved to harness/reports/data/ and the model gets only a preview plus the path (so its Python loads the file); broken tool calls get their own retry budget of 4, not counted in the 10 turns). The server adds the current UTC time and an ISO-timestamp instruction to every prompt (`with_context`). The answer area draws a chart (Recharts) and a table; Unix-second times are converted to Finnish time. Host and Origin
checks keep other websites out (tests in tests/test_harness_server.py). Not available on Vercel (it says how to start the server). Upstream files were reformatted by the editor (ruff style, no logic change). Tested 7 Nov: works with gemma-4 E4B Q8 (32k ctx) via the Llama app; the user's Fingrid key is in harness/key.txt (git-ignored; never print or commit it). Forecast quality is weak (small model, naive line extrapolation); the harness is a live demo, the LightGBM model stays the entry. Its dependencies are the `harness` group in pyproject.toml (the upstream requirements.txt was not copied).
Local edits to the upstream code (noted in harness/README.md): uv in the docstring instead of pip; `--progress` (also logs `[think]` reasoning lines); each answer's ```csv block written automatically to
`harness/reports/prediction.csv` (data rows) and `harness/reports/prediction.md` (the answer with a readable table), and `harness/report.py <answer.txt>` does the same offline;
the CLI no longer prompts for keys. API keys are asked from the website: the Harness panel shows an input field for each key that is missing (FINGRID_API_KEY, ENTSOE_API_KEY; the server runs llama.cpp, so no OpenRouter key), POSTs it to the server's `/api/keys`, which appends `NAME=value` to `harness/key.txt` (0600, git-ignored) and sets it in the run's
environment; values are never sent back to the page. GET `/api/keys` and `/api/info` report only which names are set. Command-line users put the same lines in `key.txt` by hand.

## Decisions and open questions
- Extra Fingrid history before 1 Jun (to "teach winter"): the user has a Fingrid API key (not stored; if used put it in `.secrets/fingrid.env`, git-ignored)
  and says the organisers allow extra data. NOT done. Obstacles: no spot price before June, pricing rules changed 1 Jun, ENTSO-E needs a token, test
  month is October. Agreed next step if pursued: the cheap learning-curve check (EXPERIMENTS.md section 5) before any download.
- Weather (cloud/sunlight) switches need data that is not in the package; the switches only show Fingrid's solar/wind/consumption forecasts.
- Harness prediction: its code is now in harness/ (see the Harness section); not yet connected to the chart (needs a converter and a decision on showing live forecasts); weak results so far (EXPERIMENTS.md section 8).
- The user decided to develop the website on this laptop (friends only need `web/public/data/` + Node, see README).
- LUMI: not set up (no access yet; local training takes about a minute). `scripts/train_cpu.sbatch` is untested with a placeholder project ID. If
  asked: `lumi-workspaces` for the project ID, then give rsync commands excluding .git/.venv/outputs.
- Slides (5-8), demo video (max 5 min) and the platform upload are for the user; I can draft slide/demo content from REPORT.md.

## Status (7 Nov 2026, evening)
- Submission `outputs/final/forecast_backtest.csv` exists, passes the organiser validator, and was reproduced byte-identical on a fresh clone
  (sha256 starts 4f396b56dd9bae1d). It is not in git (upload it from the laptop). Final model: LightGBM, validation MAE 43.21 vs baseline 66.20.
- Git: the harness work from 7-8 Nov (reasoning display, data-as-files, retry budget, period buttons hidden on Harness) may be uncommitted: run `git status -sb` and `git log --oneline -3`; the user pushes himself, check for "ahead".
- Variant JSON files exist locally (web/public/data/, about 74 MB, git-ignored).
- Website hosted on Vercel for a demo: project `imbalance-forecast-demo`, https://imbalance-forecast-demo.vercel.app (public link, deployed with
  `cd web && npm run build && npx vercel deploy dist --prod`; it may show an older version). MUST be deleted after the event (`npx vercel remove imbalance-forecast-demo`,
  Nord Pool licence). Its Harness page only explains how to start the local server.
- Harness: author is the user's teammate (licence concern settled). The panel works end to end with the local gemma model (reasoning per step confirmed by the user); forecasts so far were weak or wrong (see EXPERIMENTS.md
  section 8); the data-as-files change and the 12h prompt wording were not yet checked on a full run. Needs: Llama app running, `./scripts/start_harness.sh` restarted after any change to harness/server.py.
- Still to do by the user before Sun 8 Nov 10:00: upload the CSV + REPORT.md + SOURCES.md + repo link, slides (5-8), demo video (max 5 min). Delete data after the event.

## Next ideas (none started)
Slides and demo script (the jury part is 20 points); learning-curve check; direction-aware price model; more direction features; spike probabilities from extra quantiles. Already tested, no gain: fixed p_none and spike base-rate shift (EXPERIMENTS.md section 7).
