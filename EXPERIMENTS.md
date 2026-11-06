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

- **Extra history before 1 Jun (Fingrid key available):** no spot price exists for earlier months in the package, the pricing
  rules changed on 1 Jun 2026 (volume-weighted mFRR/aFRR price), and ENTSO-E series would need a token. Judged not worth the
  risk of a timing mistake with the availability rule.
- **Weather data (Open-Meteo Single Runs):** allowed with the publication delay added, but not tried; Fingrid's day-ahead wind
  and solar forecasts are used instead.
- **LUMI:** not needed (training takes about a minute locally). `scripts/train_cpu.sbatch` exists but is untested.

## 5. Ideas not yet tried

- Direction-aware price model: price under up- and down-regulation modelled separately and mixed with the direction probability.
- Calibrating the spike probabilities on held-out data (base-rate shift).
- Extra direction features (mFRR activation trends over several scales, neighbour price gaps).
