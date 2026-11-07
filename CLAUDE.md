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
- `uv run pytest -q` (23 tests) and `cd web && npx vitest run` (9 tests).
- `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` -> validation month, scored vs the organisers' baseline, outputs/X/.
- `uv run scripts/run_rolling.py [--tag X] [--ref TAG] [--set key=value ...]` -> 8 weekly windows; judge model changes here.
- `uv run scripts/run_final.py` -> outputs/final/forecast_backtest.csv and runs the organiser validator.
- `uv run scripts/exp_postproc.py` -> post-processing experiments on the 8 windows (section 7 of EXPERIMENTS.md).
- `uv run scripts/run_variants.py` -> the 7 model variants behind the viewer's input switches (about 12 min).
- Organiser tools: `uv run python -I starter_package_v1/{validate_submission,score,make_templates}.py`.
- Viewer: `./scripts/start_web.sh` (http://localhost:5173). `scripts/export_web_data.py` writes web/public/data/{validation,final}.json from outputs/.

## Model (details in REPORT.md)
Target = imbalance minus spot of the target quarter-hour. Six LightGBM models: quantile p10/p50/p90, 3-class direction, two spike models (+-50 EUR/MWh
vs spot). 8 leaves, extra-trees, 6 seeds, rounds from a time-ordered inner split (14 d, 10 h embargo), p10/p90 shifted by conformal offsets.
`model.drop_features` in the config leaves features out (used for the viewer switches). Near the ceiling of this data (EXPERIMENTS.md).

## Web viewer (web/, React + TypeScript + Vite + Recharts + Tailwind 4; tests Vitest + jsdom)
- TypeScript (strict): `src/App.tsx`, `src/types.ts` (forecast file shapes), `src/main.tsx`, tests in `web/test/*.tsx`. Check types with `cd web && npm run typecheck`; `npm run build` type-checks first. Keep new code typed (no `any`).
- Layout: one screen, no scrolling on large screens; wave background (light-blue wave + orange hill); title row, period buttons, two method boxes,
  a fixed-height summary strip (summary, drivers, number chips), then the chart centred and as large as possible with time controls above it
  and the input switches stacked vertically in a narrow column left of the chart (the user asked for this; no other left column). Do not define components inside `App` (it remounts the controls; a test guards this).
- Methods: boxes "Machine-learning model" (was "Current model") and "Harness prediction" (METHODS in App.tsx). Harness has no data yet: it reads
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

## Decisions and open questions
- Extra Fingrid history before 1 Jun (to "teach winter"): the user has a Fingrid API key (not stored; if used put it in `.secrets/fingrid.env`, git-ignored)
  and says the organisers allow extra data. NOT done. Obstacles: no spot price before June, pricing rules changed 1 Jun, ENTSO-E needs a token, test
  month is October. Agreed next step if pursued: the cheap learning-curve check (EXPERIMENTS.md section 5) before any download.
- Weather (cloud/sunlight) switches need data that is not in the package; the switches only show Fingrid's solar/wind/consumption forecasts.
- Harness prediction: a teammate's second method, to be added later as JSON files (see above); an exporter can be written once its format is known.
- The user decided to develop the website on this laptop (friends only need `web/public/data/` + Node, see README).
- LUMI: not set up (no access yet; local training takes about a minute). `scripts/train_cpu.sbatch` is untested with a placeholder project ID. If
  asked: `lumi-workspaces` for the project ID, then give rsync commands excluding .git/.venv/outputs.
- Slides (5-8), demo video (max 5 min) and the platform upload are for the user; I can draft slide/demo content from REPORT.md.

## Status (7 Nov 2026)
- Submission `outputs/final/forecast_backtest.csv` exists, passes the organiser validator, and was reproduced byte-identical on a fresh clone
  (sha256 starts 4f396b56dd9bae1d). It is not in git (upload it from the laptop).
- Git: all work is committed (run `git log --oneline -3` and `git status -sb` for the exact state). Pushing to GitHub is the user's step: he pushes himself or
  says so; check `git status -sb` for "ahead". The input switches, the redesigned one-screen viewer with smooth time/Play and the fixed price axis, and the
  doc rewrite are part of the commit made on 7 Nov 2026.
- Variant JSON files exist locally (web/public/data/, about 74 MB, git-ignored).

## Next ideas (none started)
Slides and demo script (the jury part is 20 points); learning-curve check; direction-aware price model; more direction features; spike probabilities from extra quantiles. Already tested, no gain: fixed p_none and spike base-rate shift (EXPERIMENTS.md section 7).
