import type { InputId, MethodKey, PeriodKey } from "./types";

export const QUARTER_HOUR_MS = 15 * 60 * 1000;
export const HOUR_MS = 4 * QUARTER_HOUR_MS;
/** Real prices are published about 75 minutes after a quarter-hour starts. */
export const PUBLICATION_DELAY_MS = 75 * 60 * 1000;
/** Time between animation frames while playing or gliding (about 30 per second). */
export const FRAME_INTERVAL_MS = 33;
export const PLAYBACK_SPEEDS = [1, 3, 10] as const;

// The two ways of predicting. "harness" has no forecast files yet: when its two files (same format as validation.json / final.json)
// appear in frontend/public/data/, the tab switches the chart to them automatically.
export const METHODS: Record<MethodKey, { title: string; files: Record<PeriodKey, string> }> = {
  current: { title: "Machine-learning model", files: { validation: "validation", final: "final" } },
  harness: { title: "Harness prediction", files: { validation: "harness_validation", final: "harness_final" } },
};

// Input switches of the machine-learning model. Each combination is a separately trained model variant computed by
// backend/scripts/run_variants.py; the variant key has one digit per switch (1 = on, 0 = off), "111" is the normal model.
export const INPUT_SWITCHES: { id: InputId; label: string }[] = [
  { id: "solar", label: "Solar forecast" },
  { id: "wind", label: "Wind forecast" },
  { id: "consumption", label: "Consumption forecast" },
];
export const ALL_INPUTS_ON_KEY = "111";

export const PERIODS: Record<PeriodKey, { label: string }> = {
  validation: { label: "Validation 7 Sep – 4 Oct" },
  final: { label: "Test forecast 5 Oct – 1 Nov" },
};

/** Feature group (as named by src/features.py) -> plain words, for the "Why" line of the chart's hover window. */
export const DRIVER_DESCRIPTIONS: Record<string, string> = {
  spot_price: "the day-ahead price of electricity",
  consumption_forecast_da: "the forecast of electricity consumption",
  wind_forecast_da: "the wind power forecast",
  solar_forecast_da: "the solar power forecast",
  residual_load_forecast: "the electricity demand left after wind and solar",
  latest_imbalance_price: "the latest imbalance prices",
  imbalance_minus_spot_history: "how far recent imbalance prices were from the day-ahead price",
  mfrr_direction_history: "whether the grid recently needed more or less power",
  mfrr_prices_and_activation: "prices and use of the manual balancing reserve",
  afrr_activity: "use of the automatic balancing reserve",
  cross_border_flows: "electricity flows to and from neighbouring countries",
  neighbour_imbalance_prices: "imbalance prices in Sweden and Estonia",
  same_time_previous_days_imbalance: "the imbalance price at the same time on previous days",
  consumption_actual: "measured electricity consumption",
  production_actual: "measured electricity production",
  neighbour_load_forecasts: "consumption forecasts of neighbouring countries",
  fi_ee_capacity: "the transmission capacity between Finland and Estonia",
  calendar: "the time of day and the weekday",
  forecast_horizon: "how far ahead the hour is",
};
