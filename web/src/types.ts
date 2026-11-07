/** Shape of the forecast files in web/public/data (written by src/exports.py `web_payload`). */
export type Cell = string | number | null;
export interface Payload {
  name: string;
  hasActuals: boolean;
  cols: string[];
  rows: Cell[][];
}
/** One forecast row (one origin, one quarter-hour) after the columns are matched with the values. */
export interface Row {
  forecast_origin_utc: string;
  delivery_start_utc: string;
  step: number;
  p10: number;
  p50: number;
  p90: number;
  p_up: number;
  p_down: number;
  p_none: number;
  p_spike_high: number;
  p_spike_low: number;
  top_drivers?: string;
  actual_imbalance_price?: number | null;
  [column: string]: Cell | undefined;
}
export type NumKey = "p10" | "p50" | "p90";
/** One point of the chart (times in ms since 1970). */
export interface ChartPoint {
  ms: number;
  base: number | null;
  width: number | null;
  p10: number | null;
  p50: number | null;
  p90: number | null;
  prevBase: number | null;
  prevWidth: number | null;
  prevP50: number | null;
  realKnown: number | null;
  realLater: number | null;
  why: string;                     // the driver groups behind this point (SHAP), for the hover window
}
export type MethodKey = "current" | "harness";
export type SetKey = "validation" | "final";
export type ToggleId = "solar" | "wind" | "consumption";
export interface VariantIndex {
  metrics?: Record<string, { mae: number }>;
  [k: string]: unknown;
}
