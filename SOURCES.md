# Sources, services, models and licences

| What | Use | Licence / rights |
|---|---|---|
| Fingrid Open Data (imbalance price 319, mFRR 244/106/375/376/369, aFRR 347/348, consumption 124, production 74, DA forecasts 165/246/247, flows 61/57/60/55) | inputs, via organiser starter package | CC BY 4.0 |
| ENTSO-E Transparency Platform (17.1.g imbalance SE1/SE3/EE, 6.1.b load forecasts, 11.1 FI-EE capacity) | inputs, via starter package | CC BY 4.0 (free re-use list) |
| Nord Pool day-ahead spot price, Finland | feature + spike reference, via starter package | Licensed to Turku Energia; hackathon use only, not redistributed, not in the repo, deleted after the event |
| Calendar series (weekday, hour, Finnish holidays, DST) | inputs, via starter package | provided by organiser |
| Organiser scripts (`validate_submission.py`, `score.py`, `make_templates.py`, baseline notebook) | validation/scoring; baseline logic ported to `src/baseline.py` | provided by organiser for the hackathon |
| No external data added | no weather API, no Open-Meteo, no Fingrid history before 1 June | – |

Software: Python, pandas (BSD-3), numpy (BSD-3), pyarrow (Apache-2.0), LightGBM (MIT), scikit-learn (BSD-3),
PyYAML (MIT), pytest (MIT), uv (MIT/Apache-2.0), optional Streamlit (Apache-2.0) for the older viewer. Models are trained from scratch; no
pretrained or third-party models. Web test tools: Vitest, jsdom, Testing Library (all MIT). No external data was added: the Fingrid history before
1 June and weather data were considered and not used (see `EXPERIMENTS.md` section 4).

## Web viewer (`web/`)
| Component | Use | Licence / rights |
|---|---|---|
| "The Reading Room" design system (colours, fonts, Card/Button/Stat/Alert/Badge/Hills components) | page styling, copied into `web/src/design-system/` from a Lovable-generated template supplied by the team | No licence file came with it; generated with Lovable for Turku Energia branding, used with the team's permission (confirm before publishing the code) |
| React, Recharts, Vite, Tailwind CSS, tw-animate-css, clsx, tailwind-merge | UI, charts, build, styling | MIT |
| class-variance-authority | component variants | Apache-2.0 |
| @radix-ui/react-slot | button `asChild` helper | MIT |
| Fira Sans Extra Condensed (headlines), Libre Franklin (body, stands in for Franklin Gothic Book), Source Serif 4 (key figures, stands in for Century Schoolbook), all loaded from Google Fonts | typography per the Turku Energia graphic guidelines (the brand fonts Trade Gothic, Franklin Gothic Book and Century Schoolbook are named first in the font stack but are not shipped; they are used only where installed) | SIL Open Font License 1.1 |
| "Turku Energian graafinen ohjeisto" (Sep 2024), supplied by the team | colours, typography and tone rules followed by the viewer; no logo or images from it are used | internal brand guide, not redistributed |

Of the template, only the design system was used. Its TanStack Start, Cloudflare, `lovable-tagger` and preview-plugin parts were left out.
