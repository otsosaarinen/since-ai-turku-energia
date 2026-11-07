# CLAUDE.md — Turku Energia imbalance price forecast (Since AI 2026)

Forecast the Finnish imbalance price (`fi_imbalance_price`) 40 quarter-hours (10 h) ahead from every full-hour origin. Backtest 5 Oct–1 Nov 2026 =
673 origins x 40 = 26,920 rows -> `forecast_backtest.csv`. Data is UTC; the web viewer shows Finnish time and dd/mm/yyyy.

## Where facts live (do not copy numbers here, they drift)
- README.md: setup, commands, headline results. REPORT.md: reasoning, validation vs test, scores. EXPERIMENTS.md: every test with numbers.
- SOURCES.md: data, services, components, licences. `backend/configs/default.yaml`: periods, seeds, LightGBM settings.
- `backend/harness/README.md`: harness files, safety, local edits. `frontend/README.md`: frontend setup, settings, deploy.

## HARD RULES (violation = score 0 / code is audited)
- At origin t use a row only if `first_usable_origin_utc <= t`. Build every feature from `AvailabilityIndex.at(origin)` (backend/src/availability.py) ONLY;
  compute lags/rolling/latest AFTER filtering. Never touch the unfiltered table.
- Train only on 1 Jun–4 Oct 2026. Never use test-period (after 4 Oct) rows or labels. Validation: train only with labels usable at the first
  validation origin (2026-09-06T21:00Z); labels go through `AvailabilityIndex.labels(..., known_at=cutoff)`. A training origin o is usable at
  cut-off c only if o + 11 h <= c (all 40 labels published).
- Target quarter-hours' own actuals are never features. aFRR series are sparse: no row = no activation; never forward-fill.
- The briefing PDF (~/Downloads/Turku_Energia_Imbalance_Price_Challenge_Briefing.pdf, slides 11 and 25) is the authority: other open/paid data is
  allowed if sources and licences are listed, but test-period data is never used for training. No Open-Meteo Historical Forecast API.
- `backend/data/spot_nordpool.csv` (Nord Pool) is hackathon-only: never print its rows, commit, share or export spot values. `data/`, `outputs/`,
  `starter_package_v1/`, `*.csv`, `*.parquet`, `*.pkl`, `*.zip`, `.env`/`.secrets/`, `frontend/public/data/` are git-ignored. Delete the data after the event.
  The GitHub repo (otsosaarinen/since-ai-turku-energia) is PUBLIC: check `git status` before any commit; never add data, outputs or keys.
- `backend/starter_package_v1/` is read-only reference. Write all code outside it. Never modify files in ~/Downloads.
- Do not commit or push unless the user asks. Do not write files when the user says to keep the repo clean.

## Working with the user (Otso)
- Otso owns the model work; teammates build the frontend. He is not an ML or electricity-market expert: explain in plain language.
- Say what he must run himself and give exact commands. Say honestly when something is a guess or not verified (e.g. "not seen rendered").
- He uses Safari on macOS and sends screenshots. There is no headless browser here: test web changes with Vitest/jsdom only.
- Keep answers short: state what was done and what is uncommitted. He pushes himself.

## Layout
- `backend/`: Python package (`src/`, editable, uv project), `scripts/`, `tests/`, `configs/`, `harness/` (package), `data/`, `outputs/`, `starter_package_v1/`.
- `frontend/`: Next.js 16 (App Router), React 19, TypeScript strict, Recharts, Tailwind 4. Tests in `frontend/test/` (Vitest + jsdom).
- `frontend/src`: `app/` (layout, page), `features/forecast/` (viewer), `features/harness/` (Harness tab), `lib/` (config, theme, contrast, styles,
  chartColors, finnishTime), `components/Icon.tsx`, `design-system/` (copied from a Lovable template; only the design system was used).
- One settings file: `.env` in the repo root (template `.env.example`, git-ignored). `./dev.sh` is the one start command.

## Commands
Run backend commands from `backend/` (`uv sync` first; macOS needs `brew install libomp`, done).

| Task | Command |
|---|---|
| Start everything (data export, harness server, site on :5173) | `./dev.sh` (`--no-harness` skips the harness) |
| Backend tests | `cd backend && uv run pytest -q` |
| Python lint | `cd backend && uv run ruff check .` |
| Frontend tests | `cd frontend && npx vitest run` |
| Frontend lint, types, build | `cd frontend && npm run lint`, `npm run typecheck`, `npm run build` |
| Validation month vs baseline | `uv run scripts/run_validation.py [--tag X] [--set model.key=value]` |
| 8 weekly windows (judge model changes here) | `uv run scripts/run_rolling.py [--tag X] [--ref TAG] [--set key=value]` |
| Final submission file + organiser validator | `uv run scripts/run_final.py` -> `outputs/final/forecast_backtest.csv` |
| Post-processing experiments | `uv run scripts/exp_postproc.py` |
| The 7 variants behind the input switches (about 12 min) | `uv run scripts/run_variants.py` |
| Website data from outputs/ | `uv run scripts/export_web_data.py` -> `frontend/public/data/` |
| Organiser tools | `uv run python -I starter_package_v1/{validate_submission,score,make_templates}.py` |

- Current counts (8 Nov): 148 backend tests, 170 frontend tests, ruff and eslint clean. Update these when they change.
- Do not run the training scripts just to check something; they are slow and overwrite outputs.

## Model (details in REPORT.md)
- Target = imbalance minus spot of the target quarter-hour. Six LightGBM models: quantile p10/p50/p90, 3-class direction, two spike models (+-50 EUR/MWh vs spot).
- 8 leaves, extra-trees, 6 seeds, rounds from a time-ordered inner split (14 d, 10 h embargo), p10/p90 shifted by conformal offsets.
- `model.drop_features` in the config leaves features out (used for the viewer switches). The model is near the ceiling of this data (EXPERIMENTS.md).
- Input switches: groups in `backend/src/features.py` TOGGLE_GROUPS; 8 variants (key digits = solar, wind, consumption; 111 = normal model).
- Residual-load features are dropped whenever any group is off. Weather switches are not possible: no weather data in the package.

## Frontend rules
- No `any`. Do not define components inside another component (it remounts the controls; a test guards this).
- The address carries the tab: `?method=harness`, plain for Machine learning (default; a test guards it).
- Machine-learning tab on large screens (lg, 1024 px+): one screen, no scrolling. The Harness tab is a normal scrolling page.
- Below lg: one scrolling column. Pitfall: `flex-1` on a column child collapses the chart height, so the chart box uses `lg:flex-1` only.
- The price axis is computed once per loaded file and must not move while playing (a test guards this). Rare spikes are clipped.
- Time is fractional: the axis slides, neighbouring forecasts are blended, Play steps 1/3/10 forecast hours per second and stops at the end.
- Real-price lines: solid "known" and dashed "after forecast", named in the legend and tooltip.
- Text areas have fixed heights so changing numbers never shift the chart. The summary strip is short on purpose: do not add text (user wants less).
- Wording is plain language (no "p50", "in band"). Do not add `Info` tooltips (the user found them annoying).
- Not seen on a real phone or in Safari after the redesign: only code and tests were checked.

## Brand and UI rules (guide: ~/Downloads/Graafinen ohjeisto.pdf, web pp. 12-14, 48-49)
- Enforced by tests: contrast (AA), style rules, typography, no emoji, colours from tokens only. Run `npx vitest run` after any style change.
- White base, orange as accent, blue/grey structure. Orange surfaces with white text use #B46000; bright #F59B00 is decoration only.
- Forecast line deep orange #C96A00; real prices red; likely range blue #46BEDC; earlier forecast grey.
- Headlines: Fira Sans Extra Condensed, bold capitals ending with a full stop. Never text on plain orange, never black on orange.
- Do NOT build a logo from an orange bar + text (forbidden). Ask the user for the official digital logo file if a logo is wanted.
- Team name "Perjantain kevätrulla" sits under the title.

## Harness (backend/harness/, details and safety in its README.md)
- Copy of https://github.com/rogue-agent/livelectroray at b44314d, written by a teammate (licence concern settled). Do not edit upstream logic without noting it in its README.
- It is a live 24 h / 7 d analyst, not a backtest. Its CSV cannot fill the website's harness JSON without a converter; not connected to the chart.
- Forecasts so far are weak (EXPERIMENTS.md section 8). The LightGBM model stays the entry; the harness is a live demo.
- Run: `./dev.sh` (server on 127.0.0.1:8765, reached through the `/harness-api` rewrite in `frontend/next.config.ts`). Needs the Llama app on localhost:9931 with context >= 16k.
- Models: the panel offers only ids containing `E4B` (`HARNESS_MODEL_FILTER`). Restart `./dev.sh` after any change to harness code.
- Keys (`FINGRID_API_KEY`, `ENTSOE_API_KEY`) live in the root `.env`; the Settings box can save them there. Never print or commit them; the server never returns them.
- Audited 8 Nov: `run_python` runs with a scrubbed environment (no API keys) and, on macOS, inside a sandbox. The main risk is prompt injection from fetched web data.
- Open decision: set `HARNESS_PYTHON_NETWORK=0` (cuts network for model code; then `zones.cf()` stops working).
- `HARNESS_AUTO_RECALC=0` stops alert-triggered runs. Known unfixed bug: `nordpool_price` ignores its start/end parameters.
- Do not change the progress line format `[turn k/n]`, `[tool]`, `[result]`, `[think]`, `[done]`, `[stop]`: `frontend/src/features/harness/lib/progressSteps.ts` parses it.
- Hosted demo: set `NEXT_PUBLIC_HIDE_HARNESS=true` (the Harness tab and proxy disappear).

## Decisions and open questions
- Extra Fingrid history before 1 Jun was NOT done. Obstacles: no spot price before June, pricing rules changed 1 Jun, ENTSO-E needs a token.
  If pursued, do the cheap learning-curve check first (EXPERIMENTS.md section 5). Any key goes in `.env`, never in code.
- LUMI is not set up (no access; local training takes about a minute).
- The frontend is developed on this laptop. Friends need only `frontend/public/data/` and Node (README.md).

## Status (8 Nov 2026)
- Submission `backend/outputs/final/forecast_backtest.csv` was uploaded on 7 Nov and is unchanged (sha256 starts 4f396b56dd9bae1d). It is not in git.
- Work is on branch `nextjs-frontend` (Next.js frontend, backend/ restructure, harness package). Many changes are uncommitted: run `git status -sb`. Ask before committing.
- Vercel: the old Vite demo (`imbalance-forecast-demo`) must be deleted after the event (Nord Pool licence). The user connects the new GitHub -> Vercel project in the browser.
- Still to do by the user: slides (5-8), 2 min demo video, Safari check of the redesigned UI, delete data and Vercel copies after the event.
