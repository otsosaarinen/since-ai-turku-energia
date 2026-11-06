# Evaluation report

## Reasoning chain
1. **What drives the price.** The imbalance price is spot-referenced: up-regulation puts it above the day-ahead
   spot price, down-regulation below, and with no dominating mFRR direction it equals spot. We therefore predict
   `imbalance - spot(target quarter-hour)` and add spot back. Spot for the target is known (published D-1 14:00 local).
2. **What is predictable.** On validation the spread's autocorrelation is 0.74 at 15 min but ~0.09 at 1 h and ~0 after
   that; a constant "spot minus 12 EUR/MWh" already reaches MAE 43.7 versus 46.5 for plain spot, and knowing the
   direction would cut MAE to 35.4. The forecast quality is hence driven by (a) the structure known the day before
   (spot level/ramps, forecast consumption, wind, solar, residual load and their change versus the previous day) and
   (b) estimating the regulation direction, not by persistence of the last price. Error is almost flat over the 10 h horizon.
3. **Data and availability rule.** Features are built per origin from a window in which every cell with
   `first_usable_origin_utc > origin` is NaN (lags, rolling stats, "latest value" are computed after that). Groups:
   latest imbalance/spread statistics, mFRR direction history, mFRR prices/activations, aFRR counts (sparse, no
   forward fill), consumption/production and day-ahead forecast error, flows, SE1/SE3/EE imbalance prices and loads,
   FI-EE capacity, day-ahead consumption/wind/solar for the target and their change vs the previous day, spot ramps,
   calendar. Tests prove the filter equals the organiser's `rows_available_at`, that the data cut-off is <= origin,
   and that features are bit-identical when all not-yet-usable rows are deleted or overwritten with garbage.
4. **Models.** LightGBM (CPU): quantile p10/p50/p90, 3-class direction, two spike classifiers. Small trees (8 leaves),
   extra-trees mode, 6 seeds averaged per model, because the signal is weak and noisy so strong regularisation beats flexibility.
   Rounds chosen on a time-ordered inner split (last 14 days, 10 h embargo), then refit on the whole window.
   p10/p90 are shifted by conformal offsets from the same holdout, which lifted coverage from ~0.65 to ~0.79.
   Post-processing: sorted quantiles, renormalised direction probabilities, spike probabilities scaled so high+low <= 1.
5. **Explainability.** `top_drivers` = the three feature groups with the largest SHAP contribution to p50 for that row;
   `data_cutoff_utc` = latest `first_usable_origin_utc` among the data used.

## Validation (7 Sep – 4 Oct 2026; training only on data/labels usable at 2026-09-06T21:00Z)
| Metric | Baseline | Model |
|---|---|---|
| MAE p50 | 66.20 | 43.21 |
| Mean pinball p10/p90 | 24.18 | 12.42 |
| P10–P90 coverage | 0.683 | 0.787 |
| Brier spikes (mean) | 0.1132 | 0.0967 |
| Brier direction (3-class) | 0.4509 | 0.4121 |

By horizon (model): MAE 41.9 (hour 1) -> 44.3 (hour 10); pinball 11.99 -> 12.83; coverage 0.80 -> 0.78;
direction Brier 0.399 -> 0.423 (`outputs/validation/score/score_by_horizon.csv`).

## Rolling-window validation (8 weekly windows, each trained only on labels usable at its start)
One month is a noisy yardstick, so changes were judged on 8 weekly windows (`uv run scripts/run_rolling.py`).

| Window start (Finnish) | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|
| 10.08. | 19.1 | 4.44 | 0.83 | 0.0333 | 0.4148 |
| 17.08. | 43.0 | 11.34 | 0.64 | 0.1298 | 0.4718 |
| 24.08. | 32.7 | 7.17 | 0.76 | 0.1032 | 0.4297 |
| 31.08. | 32.2 | 6.80 | 0.80 | 0.0975 | 0.3740 |
| 07.09. | 48.5 | 15.75 | 0.81 | 0.0817 | 0.4189 |
| 14.09. | 43.0 | 13.41 | 0.79 | 0.0799 | 0.3773 |
| 21.09. | 48.1 | 11.09 | 0.77 | 0.1337 | 0.4892 |
| 28.09. | 33.7 | 9.03 | 0.85 | 0.0903 | 0.3627 |
| **mean** | **37.5** | **9.88** | **0.78** | **0.0937** | **0.4173** |

How much is real skill? Against trivial forecasts on the same windows: p50 MAE 37.5 vs 38.7 for "spot + typical spread" (54.3 for
persistence = the baseline method); interval pinball 19 % better than constant quantiles around spot; spike Brier 14 % better than
constant rates; direction Brier 9 % better than constant shares. Tree size, seasonal same-time-of-day features, recency weighting and
shrinking p50 toward spot gave no consistent gain; extra-trees + 6 seeds gave a small one (MAE and direction better in 6/8 windows).
The full list of experiments and numbers is in `EXPERIMENTS.md`.

## Caveats
- Spike probabilities are not perfectly calibrated: September had more high spikes (12 %) than the training summer
  (8 %), so low-probability bins under-predict. The final model also learns from September.
- Direction improves the Brier score only moderately (0.412 vs 0.451): "none" is almost never observed (0.3 %).
- Tried without benefit: see `EXPERIMENTS.md`. Differences of ~1 EUR/MWh MAE between variants are within noise.
- The final run could not be scored locally (test actuals are held by the organiser).
