# Sources, services, models and licences

| What | Use | Licence / rights |
|---|---|---|
| Fingrid Open Data (imbalance price 319, mFRR 244/106/375/376/369, aFRR 347/348, consumption 124, production 74, DA forecasts 165/246/247, flows 61/57/60/55) | inputs, via organiser starter package | CC BY 4.0 |
| ENTSO-E Transparency Platform (17.1.g imbalance SE1/SE3/EE, 6.1.b load forecasts, 11.1 FI-EE capacity) | inputs, via starter package | CC BY 4.0 (free re-use list) |
| Nord Pool day-ahead spot price, Finland | feature + spike reference, via starter package | Licensed to Turku Energia; hackathon use only, not redistributed, not in the repo, deleted after the event |
| Calendar series (weekday, hour, Finnish holidays, DST) | inputs, via starter package | provided by organiser |
| Organiser scripts (`validate_submission.py`, `score.py`, `make_templates.py`, baseline notebook) | validation/scoring; baseline logic ported to `backend/src/baseline.py` | provided by organiser for the hackathon |
| Harness code (`backend/harness/`) copied from github.com/rogue-agent/livelectroray @ b44314d | second prediction method (live, not part of the submission file) | no licence file upstream; ask the author before publishing. Its live data sources (Elering, Statnett, Fingrid, Open-Meteo, MET Norway, ENTSO-E and others, listed in `backend/harness/sources.py`) are used only when someone runs it. API keys for it (Fingrid, ENTSO-E) are read from the root `.env`, which is git-ignored |
| No external data added | no weather API, no Open-Meteo, no Fingrid history before 1 June | – |

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

Models are trained from scratch; no pretrained or third-party models.
No external data was added: the Fingrid history before 1 June and weather data were considered and not used (see `EXPERIMENTS.md` section 4).

## Web viewer (`frontend/`)
| Component | Use | Licence / rights |
|---|---|---|
| "The Reading Room" design system (colours, fonts, Card/Button/Stat/Alert/Badge/Hills components) | page styling, copied into `frontend/src/design-system/` from a Lovable-generated template supplied by the team | No licence file came with it; generated with Lovable for Turku Energia branding, used with the team's permission (confirm before publishing the code) |
| Next.js, React, Recharts, Tailwind CSS, tw-animate-css, clsx, tailwind-merge | UI, charts, build, styling | MIT (read from the installed packages) |
| ESLint, eslint-config-next, TypeScript, Vitest, jsdom, Testing Library | code checks, type checks, tests for the web viewer | MIT; TypeScript Apache-2.0 |
| class-variance-authority | component variants | Apache-2.0 |
| @radix-ui/react-slot | button `asChild` helper | MIT |
| Fira Sans Extra Condensed (headlines), Libre Franklin (body, stands in for Franklin Gothic Book), Source Serif 4 (key figures, stands in for Century Schoolbook), all loaded from Google Fonts | typography per the Turku Energia graphic guidelines (the brand fonts Trade Gothic, Franklin Gothic Book and Century Schoolbook are named first in the font stack but are not shipped; they are used only where installed) | SIL Open Font License 1.1 |
| Vercel (optional hosting of the built static site for a demo; the forecast data goes online with it, see the licence note in `README.md`) | demo link | Vercel terms of service; delete the project after the event |
| "Turku Energian graafinen ohjeisto" (Sep 2024), supplied by the team | colours, typography and tone rules followed by the viewer; no logo or images from it are used | internal brand guide, not redistributed |

Of the template, only the design system was used. Its TanStack Start, Cloudflare, `lovable-tagger` and preview-plugin parts were left out.
