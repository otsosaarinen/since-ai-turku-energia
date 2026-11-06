# Sources, services, models and licences

| What | Use | Licence / rights |
|---|---|---|
| Fingrid Open Data (imbalance price 319, mFRR 244/106/375/376/369, aFRR 347/348, consumption 124, production 74, DA forecasts 165/246/247, flows 61/57/60/55) | inputs, via organiser starter package | CC BY 4.0 |
| ENTSO-E Transparency Platform (17.1.g imbalance SE1/SE3/EE, 6.1.b load forecasts, 11.1 FI-EE capacity) | inputs, via starter package | CC BY 4.0 (free re-use list) |
| Nord Pool day-ahead spot price, Finland | feature + spike reference, via starter package | Licensed to Turku Energia; hackathon use only, not redistributed, not in the repo, deleted after the event |
| Calendar series (weekday, hour, Finnish holidays, DST) | inputs, via starter package | provided by organiser |
| Organiser scripts (`validate_submission.py`, `score.py`, `make_templates.py`, baseline notebook) | validation/scoring; baseline logic ported to `src/baseline.py` | provided by organiser for the hackathon |
| No external data added | no weather API, no Open-Meteo | – |

Software: Python, pandas (BSD-3), numpy (BSD-3), pyarrow (Apache-2.0), LightGBM (MIT), scikit-learn (BSD-3),
PyYAML (MIT), pytest (MIT), uv (MIT/Apache-2.0). Models are trained from scratch; no pretrained or third-party models.
