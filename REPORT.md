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
6. **Situational view (web viewer, `web/`).** One screen: a plain-language summary and the main drivers, the chance of a high or low price
   spike and of the grid needing more power, and a chart of the forecast, its likely range, the real price and the forecast made 3 hours
   earlier. Time can be moved to any forecast of the period (bar, date list, 1 h / 1 day steps) or played forward smoothly, so the usefulness can be
   shown over time and not only live. Three switches turn Fingrid's solar, wind and consumption forecasts on and off (each combination is a
   separately trained model, see "Input switches" below). A second prediction method ("Harness prediction") has a place in the viewer and is
   shown as soon as its forecasts are added.

## Factors affecting the forecast
How often each factor is among the three biggest drivers (SHAP) of a forecast, over all 26,920 rows of the test forecast:

| Factor | Share of forecasts |
|---|---|
| The day-ahead (spot) price | 95 % |
| How far recent imbalance prices were from the day-ahead price | 54 % |
| The wind power forecast | 52 % |
| The latest imbalance prices | 40 % |
| Use of the automatic balancing reserve (aFRR) | 21 % |
| Whether the grid recently needed more or less power (regulation direction) | 15 % |
| The consumption forecast | 13 % |
| Prices and use of the manual balancing reserve (mFRR) | 5 % |
| Imbalance prices in Sweden and Estonia | 4 % |
| The solar forecast, calendar, residual load | under 1 % each |

The factors are mostly the day-before structure (price, wind and consumption forecasts) and the most recent hour of the balancing market;
persistence beyond about one hour is weak (the spread's autocorrelation is about 0.09 at one hour). Cross-border flows, consumption and
production measurements and the FI-EE capacity are inputs too but rarely a top-three driver.

**Input switches.** Leaving out the solar, wind and consumption forecasts, in every combination, changes the validation error by at most
0.8 EUR/MWh (all three off: +0.4, 1 %), with no consistent order, so none of the three adds a measurable accuracy gain on this month; the wind
forecast looks the most useful and the solar forecast the least. Details in `EXPERIMENTS.md` section 6. Real cloud or sunlight data is not in the
model.

## Validation versus test (terms used in this report)
- **Test period (5 Oct – 1 Nov):** the real submission. The organisers hold the real prices and score `forecast_backtest.csv`; we never see them.
- **Validation month (7 Sep – 4 Oct):** a practice run of the same task on a month where we do have the real prices
  (`actuals_validation.csv`). The model is trained only on data and labels that were public at 7 Sep, forecasts every hour of the month
  without having seen its prices, and is then scored against what really happened with the organisers' `score.py`.
  It is the only way to tell whether a change to the model helps.
- **The final model also trains on the validation weeks** (allowed: they are inside the 1 Jun – 4 Oct training window), so it cannot be
  scored fairly on that month; the validation run therefore uses a separate model that stops at 6 Sep.
- **Both use the availability rule:** at every origin only rows with `first_usable_origin_utc <= origin` are visible, even though the
  data file contains the whole test month.
- **Points:** each of the four automatic criteria earns `weight x clip((baseline - ours) / (baseline - best team), 0, 1)` (weights 30, 20,
  20, 10); the best team's score is unknown to us, so points cannot be computed in advance. The jury scores reasoning (20 %) and the
  situational view (Level 2).

## How the current model is trained, and why
1. **Training examples.** One example = a past forecast origin (full hour) and one of its 40 target quarter-hours: about 150 features known
   at that hour (built from the availability-filtered window) plus the real outcome (price, direction, spike). Only origins whose 40
   outcomes were all published by the cut-off are used (final model: 2,966 origins, 118,640 rows, June to 4 Oct).
2. **Target = imbalance price minus the spot price of that quarter-hour.** The price is built around spot (above it in up-regulation,
   below in down-regulation); the level target was worse (MAE 45.9 vs 44.7).
3. **Six LightGBM models:** quantile p10, p50, p90; a 3-class direction model; two binary spike models (+-50 EUR/MWh vs spot).
   LightGBM handles mixed tabular data and missing values, has a native quantile loss and gives SHAP explanations.
4. **Small trees, extra-trees mode (8 leaves).** The signal is weak and noisy, so strong regularisation beats flexibility
   (16 leaves was worse in 0/8 windows on pinball; extra-trees was better in 6/8 on MAE and direction).
5. **Number of boosting rounds from a time-ordered hold-out:** the last 14 days before the cut-off, with a 10 h gap so no training
   target overlaps it; training stops when the hold-out error stops improving.
6. **Refit on all data with that number of rounds, 6 random seeds averaged** (reduces random variation).
7. **Interval calibration:** on the same hold-out, p10 and p90 are shifted so each is crossed about 10 % of the time; raw coverage was
   0.64 and is now 0.79 (target about 0.80).
8. **Post-processing:** sorted quantiles, direction probabilities sum to 1, spike probabilities scaled so high + low <= 1.

## Result of the organisers' `score.py` on the validation month
| Metric | Baseline | Model | Better by |
|---|---|---|---|
| MAE p50 | 66.20 | 43.21 | 35 % |
| Mean pinball p10/p90 (p10 8.01, p90 16.82) | 24.18 | 12.42 | 49 % |
| P10–P90 coverage (target about 0.80) | 0.683 | 0.787 | – |
| Spike Brier (high 0.1015, low 0.0918) | 0.1132 | 0.0967 | 15 % |
| Direction Brier (3-class) | 0.4509 | 0.4121 | 9 % |

## Validation by forecast hour (7 Sep – 4 Oct 2026; training only on data/labels usable at 2026-09-06T21:00Z)
Overall scores are in the table above.

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
- The web viewer was built to the Turku Energia graphic guidelines but has not been checked with the official logo (not supplied).
