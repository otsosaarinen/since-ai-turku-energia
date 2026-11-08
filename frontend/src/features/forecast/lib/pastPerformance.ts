import { PUBLICATION_DELAY_MS } from "../constants";
import type { Payload } from "../types";

const DAY_MS = 24 * 60 * 60 * 1000;

export interface PerformanceWindow {
  label: string;
  /** Average distance between the most likely price and the real price, EUR/MWh; null when nothing was scored. */
  averageError: number | null;
  /** Share (0..1) of real prices inside the likely range; the target is 0.8. */
  insideRange: number | null;
}

const WINDOWS: { label: string; days: number }[] = [
  { label: "Last 24 h", days: 1 },
  { label: "Last 7 days", days: 7 },
  { label: "Since the start", days: Infinity },
];

/**
 * How the forecasts did before the chosen time: every forecast made in the window, scored on quarter-hours whose real price
 * was already published at that time. Returns null when the file has no real prices (the test month).
 */
export function pastPerformance(payload: Payload, nowMs: number): PerformanceWindow[] | null {
  if (!payload.hasActuals) return null;
  const col = (name: string) => payload.cols.indexOf(name);
  const [originCol, deliveryCol, p10Col, p50Col, p90Col, actualCol] =
    ["forecast_origin_utc", "delivery_start_utc", "p10", "p50", "p90", "actual_imbalance_price"].map(col);
  const sums = WINDOWS.map(() => ({ error: 0, inside: 0, count: 0 }));
  for (const row of payload.rows) {
    const actual = row[actualCol];
    if (actual == null) continue;
    if (Date.parse(row[deliveryCol] as string) + PUBLICATION_DELAY_MS > nowMs) continue;
    const age = nowMs - Date.parse(row[originCol] as string);
    WINDOWS.forEach(({ days }, index) => {
      if (age > days * DAY_MS) return;
      const total = sums[index];
      total.count += 1;
      total.error += Math.abs((row[p50Col] as number) - (actual as number));
      if ((actual as number) >= (row[p10Col] as number) && (actual as number) <= (row[p90Col] as number)) total.inside += 1;
    });
  }
  return WINDOWS.map(({ label }, index) => {
    const { error, inside, count } = sums[index];
    return { label, averageError: count ? error / count : null, insideRange: count ? inside / count : null };
  });
}
