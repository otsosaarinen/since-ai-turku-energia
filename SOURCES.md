# Sources, services, models and licences

| What | Use | Licence / rights |
|---|---|---|
| Fingrid Open Data (imbalance price 319, mFRR 244/106/375/376/369, aFRR 347/348, consumption 124, production 74, DA forecasts 165/246/247, flows 61/57/60/55) | inputs, via organiser starter package | CC BY 4.0 |
| ENTSO-E Transparency Platform (17.1.g imbalance SE1/SE3/EE, 6.1.b load forecasts, 11.1 FI-EE capacity) | inputs, via starter package | free re-use with attribution under the ENTSO-E Transparency Platform terms |
| Nord Pool day-ahead spot price, Finland | feature + spike reference, via starter package | Licensed to Turku Energia; hackathon use only, not redistributed, not in the repo, deleted after the event |
| Calendar series (weekday, hour, Finnish holidays, DST) | inputs, via starter package | provided by organiser |
| Organiser scripts (`validate_submission.py`, `score.py`, `make_templates.py`, baseline notebook) | validation/scoring; baseline logic ported to `backend/src/baseline.py` | provided by organiser for the hackathon |
| Harness code (`backend/harness/`) copied from github.com/rogue-agent/livelectroray @ b44314d | optional live demo, not part of the submission file and not used for the scored forecasts | no licence file upstream; used with the author's (a teammate's) permission. When someone runs it, it can fetch public live data from: Elering, spot-hinta.fi, the Nord Pool Data Portal, Fingrid, ENTSO-E, Statnett, Caruna, GDACS, MET Norway and Open-Meteo (30 named sources in `backend/harness/sources.py`). API keys for it (Fingrid, ENTSO-E) are read from the root `.env`, which is git-ignored |
| A locally run language model (e.g. Google gemma-4 through llama.cpp or a llama.cpp-based local server), chosen by the user when running the Harness | only the optional Harness; not bundled, not downloaded by this repo, not used for the scored forecasts | model: Gemma terms of use of the version the user runs; llama.cpp: MIT |
| No external data added to the model | no weather API, no Open-Meteo, no Fingrid history before 1 June in the forecast model | – |

## Software

Backend (`backend/pyproject.toml`):

- Python; pandas (BSD-3), numpy (BSD-3), pyarrow (Apache-2.0), LightGBM (MIT), scikit-learn (BSD-3), PyYAML (MIT).
- Build and tools: uv (MIT/Apache-2.0), hatchling (MIT), pytest (MIT), ruff (MIT).
- Harness group (optional): openai (Apache-2.0), scipy (BSD-3), statsmodels (BSD-3).

Frontend (`frontend/package.json`):

- Next.js, React, Recharts, Tailwind CSS (with `@tailwindcss/postcss`), tw-animate-css, clsx, tailwind-merge: MIT (see the viewer table below).
- TypeScript (Apache-2.0); ESLint with eslint-config-next (MIT).
- Tests: Vitest, jsdom, Testing Library (all MIT); type packages `@types/*` (MIT).

API keys (Fingrid, ENTSO-E) are read from the root `.env`, which is git-ignored and never committed.

The scored forecast models (six LightGBM models) are trained from scratch on the organisers' data; they use no pretrained or third-party model. Only the optional Harness uses a ready-made language model (see the table).
No external data was added to the forecast model: the Fingrid history before 1 June and weather data were considered and not used (see `EXPERIMENTS.md` section 4).

## Web viewer (`frontend/`)
| Component | Use | Licence / rights |
|---|---|---|
| "The Reading Room" design system (colours, fonts, Card/Button/Stat/Alert/Badge/Hills components) | page styling, copied into `frontend/src/design-system/` from a Lovable-generated template supplied by the team | No licence file came with it; generated with Lovable for Turku Energia branding, used with the team's permission (confirm before publishing the code) |
| Next.js, React, Recharts, Tailwind CSS, tw-animate-css, clsx, tailwind-merge | UI, charts, build, styling | MIT (read from the installed packages) |
| ESLint, eslint-config-next, TypeScript, Vitest, jsdom, Testing Library | code checks, type checks, tests for the web viewer | MIT; TypeScript Apache-2.0 |
| class-variance-authority | component variants | Apache-2.0 |
| @radix-ui/react-slot | button `asChild` helper | MIT |
| Fira Sans Extra Condensed (headlines), Libre Franklin (body, stands in for Franklin Gothic Book), Source Serif 4 (key figures, stands in for Century Schoolbook), all loaded from Google Fonts | typography per the Turku Energia graphic guidelines (the brand fonts Trade Gothic, Franklin Gothic Book and Century Schoolbook are named first in the font stack but are not shipped; they are used only where installed) | SIL Open Font License 1.1 |
| Vercel (hosting of the viewer, a Next.js app built by Vercel from the GitHub repository, for a demo link) and Vercel Blob (a public store holding only the 17 forecast JSON files the viewer loads (16 forecasts plus a small index): model outputs and real imbalance prices, no spot prices) | demo link and data for the demo | Vercel terms of service; delete the project, the deployments and the Blob store after the event |
| GitHub (hosts the public repository; GitHub Actions runs the tests on every push) | code hosting and continuous checks | GitHub terms of service; the repository contains no data and no credentials |
| "Turku Energian graafinen ohjeisto" (Sep 2024), supplied by the team | colours, typography and tone rules followed by the viewer; no logo or images from it are used | internal brand guide, not redistributed |

Of the template, only the design system was used. Its TanStack Start, Cloudflare, `lovable-tagger` and preview-plugin parts were left out.
