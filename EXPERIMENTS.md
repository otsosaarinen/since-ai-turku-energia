# Experiment log

Everything we tried on the model, with the numbers, so nothing has to be re-run to know the answer.
Lower is better for MAE, pinball and Brier. "Base" below means the model as it was before the final settings.

- **Validation month** = 7 Sep – 4 Oct, trained only on data/labels usable at 2026-09-06T21:00Z (`scripts/run_validation.py`).
  The organiser's baseline there: MAE 66.20, pinball 24.18, coverage 0.683, spike Brier 0.1132, direction Brier 0.4509.
- **Rolling windows** = 8 weekly windows 10 Aug – 4 Oct, each trained only on labels usable at its start
  (`scripts/run_rolling.py`). One month is noisy (weekly MAE ranges from 19 to 49), so decisions were made on these.

## 1. Single-month validation (early model)

| Variant | MAE | Pinball | Coverage | Spike | Direction |
|---|---|---|---|---|---|
| First model (24 leaves, 1 seed, no calibration) | 44.71 | 12.85 | 0.642 | 0.0976 | 0.4203 |
| Predict the price level instead of the spread | 45.86 | 13.07 | 0.704 | 0.0976 | 0.4203 |
| Learning rate 0.02 | 44.31 | 12.94 | 0.640 | 0.0986 | 0.4226 |
| 8 leaves | 44.52 | 12.57 | 0.667 | 0.0968 | 0.4219 |
| min 400 rows per leaf | 43.84 | 13.14 | 0.636 | 0.0985 | 0.4197 |
| 8 leaves + hour-boundary ramp features | 44.12 | 12.52 | 0.660 | 0.0965 | 0.4197 |
| + 3 seeds, no interval calibration | 43.53 | 12.56 | 0.676 | 0.0965 | 0.4149 |
| + 3 seeds + interval calibration | 43.60 | 12.34 | 0.805 | 0.0965 | 0.4149 |
| Recency weighting, half-life 30 days | 44.66 | 12.41 | 0.807 | 0.0977 | 0.4214 |
| Recency weighting, half-life 60 days | 43.85 | 12.39 | 0.807 | 0.0970 | 0.4217 |
| Recency weighting, half-life 120 days | 43.91 | 12.36 | 0.808 | 0.0977 | 0.4169 |

Conclusions: the spread target is better than the level; ramp features, seeds and interval calibration helped; recency
weighting did not help (kept off); bigger trees and lower learning rate did not help.

## 2. Rolling windows (8 weeks), compared with base

Base mean over the 8 windows: MAE 37.675, pinball 9.959, coverage 0.771, spike 0.0939, direction 0.4190.
Differences below are "variant minus base" (negative = better); brackets = windows where it was better.

| Variant | MAE | Pinball | Spike | Direction | Decision |
|---|---|---|---|---|---|
| 16 leaves | +0.282 (3/8) | +0.073 (0/8) | +0.0007 | +0.0037 | worse |
| 4 leaves | +0.258 (2/8) | -0.064 (4/8) | -0.0005 | -0.0002 | no gain |
| min 80 rows per leaf | -0.011 (5/8) | -0.030 (4/8) | +0.0004 | +0.0009 | no gain |
| no interval calibration | -0.028 (2/8) | +0.009 (5/8) | 0 | 0 | neutral; kept (it sets coverage near 0.8) |
| 7-day same-time-of-day features | -0.047 (3/8) | +0.032 (3/8) | +0.0004 | +0.0009 | no gain, reverted |
| lambda_l2 = 30 | -0.026 (3/8) | +0.004 (3/8) | +0.0007 | +0.0005 | no gain |
| feature_fraction 0.4 | -0.058 (6/8) | -0.012 (5/8) | +0.0007 | -0.0002 | tiny |
| extra-trees | -0.126 (6/8) | -0.065 (4/8) | -0.0001 | -0.0015 (6/8) | small gain |
| extra-trees + feature_fraction 0.4 | -0.019 (4/8) | -0.150 (6/8) | -0.0003 | -0.0008 | small |
| extra-trees + learning rate 0.08 | -0.181 (5/8) | -0.109 (5/8) | 0.0000 | -0.0004 | similar |
| **extra-trees + 6 seeds (adopted)** | **-0.145 (6/8)** | **-0.080 (5/8)** | **-0.0002** | **-0.0017 (6/8)** | **adopted** |

Adopted model, 8-window mean: MAE 37.53, pinball 9.88, coverage 0.78, spike 0.0937, direction 0.4173.

## 3. Analyses

- **Persistence fades fast.** Spread autocorrelation: 0.74 at 15 min, 0.09 at 1 h, about 0 after. Direction autocorrelation: 0.42 at 1 h, 0.10 at 10 h.
- **Trivial forecasts on the 8 windows (mean MAE):** persistence 54.3 (the baseline method), plain spot 40.6, spot + typical
  spread 38.7, spot + typical spread by hour 38.6, our model 37.5. So most of the gain over the baseline comes from using the spot
  price; our extra gain over "spot + typical spread" is about 1.1 EUR/MWh.
- **Skill versus constants (base run):** interval pinball 19 % better, spike Brier 14 % better, direction Brier 9 % better.
- **Validation month:** oracle direction would cut MAE from 43.7 to 35.4 (an upper bound, not reachable).
- **Shrinking p50 toward spot + typical spread:** weight 0.25 → MAE 38.25, 0.5 → 37.92, 0.75 → 37.70, 1.0 → 37.63, 1.25 → 37.70.
  Full weight on the model is best, so the p50 is not noisy.
- **Probability reliability (validation month):** spike probabilities were under-predicted at the low end because September had
  more high spikes (12 %) than the summer training data (8 %).

## 4. Decisions not pursued

- **Extra history before 1 Jun (the user has a Fingrid API key, not stored in the repo):** the idea is to teach the model winter price levels.
  Judged risky and probably not useful, not done: no spot price exists for earlier months in the package, the pricing rules changed on
  1 Jun 2026 (volume-weighted mFRR/aFRR price), ENTSO-E series would need a token, the test month is October (not winter) and a winter
  benefit could not be validated. The briefing PDF (slides 11 and 25) allows other open data if sources and licences are listed, and the
  user says the organisers confirmed it. Open question: run the cheap learning-curve check (section 5) first; only if more training
  data clearly helps, find a licensed spot source, rebuild `first_usable_origin_utc` for old rows and add a regime flag.
- **Weather data (Open-Meteo Single Runs):** allowed with the publication delay added, but not tried; Fingrid's day-ahead wind
  and solar forecasts are used instead.
- **Cloud cover / sunlight switches on the website:** need real weather data, which is not in the package (Open-Meteo Single Runs would need the
  publication delay added); the switches therefore only show the effect of Fingrid's solar, wind and consumption forecasts (section 6).
- **LUMI:** not needed (training takes about a minute locally). `scripts/train_cpu.sbatch` exists but is untested.

## 5. Ideas not yet tried

- **Learning-curve check (cheap, about 15 minutes, no new data):** rerun the 8 rolling windows training on only the last 50 %, 75 % and 100 % of each
  window's history. If scores do not improve with more data, older data from another price regime is unlikely to help either.
- Direction-aware price model: price under up- and down-regulation modelled separately and mixed with the direction probability.
- Calibrating the spike probabilities on held-out data (base-rate shift).
- Extra direction features (mFRR activation trends over several scales, neighbour price gaps).

## 6. Input toggles: leaving out Fingrid's solar, wind and consumption forecasts (validation month)

`scripts/run_variants.py` trains the model without each combination of the three day-ahead forecast groups (same settings and seeds, trained only
on data usable at 6 Sep). Residual-load features combine all three, so they are removed whenever any group is off. The web viewer shows these
variants as three switches above the chart. Lower is better.

| Variant | MAE | vs all on | Pinball | Coverage | Spike Brier | Direction Brier | Features removed |
|---|---|---|---|---|---|---|---|
| all three on (the normal model) | 43.21 | – | 12.42 | 0.787 | 0.0967 | 0.4121 | 0 |
| consumption off | 43.28 | +0.06 | 12.43 | 0.782 | 0.0966 | 0.4070 | 15 |
| wind off | 43.88 | +0.66 | 12.47 | 0.785 | 0.0970 | 0.4151 | 12 |
| solar off | 43.46 | +0.25 | 12.45 | 0.788 | 0.0970 | 0.4096 | 10 |
| wind + consumption off (only solar on) | 43.08 | -0.13 | 12.46 | 0.772 | 0.0969 | 0.4131 | 21 |
| solar + consumption off (only wind on) | 43.66 | +0.45 | 12.43 | 0.784 | 0.0965 | 0.4085 | 19 |
| solar + wind off (only consumption on) | 43.52 | +0.31 | 12.48 | 0.794 | 0.0972 | 0.4155 | 16 |
| all three off | 43.61 | +0.40 | 12.52 | 0.788 | 0.0975 | 0.4114 | 25 |

Reading: all eight models are within 0.8 EUR/MWh in MAE (43.08 to 43.88) and 0.1 in pinball, with no consistent order (two variants
without inputs are even slightly better than the full model). Removing all three forecasts costs only 0.40 EUR/MWh (1 %), and one-month
differences of about 0.1 EUR/MWh are noise (rolling windows). The wind forecast looks the most useful (+0.66 when off alone), the solar
forecast the least. The model leans mostly on the spot price and recent prices: in the final test forecast the spot price is among the top
three drivers of 95 % of the forecasts, the wind forecast of 52 % and the solar forecast of 0.5 %. This is also why real weather data (cloud
cover, sunlight) is unlikely to add much; it was not tested because it is not in the data.
