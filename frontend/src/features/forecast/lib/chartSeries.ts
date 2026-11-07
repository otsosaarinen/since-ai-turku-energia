import { HOUR_MS, PUBLICATION_DELAY_MS, QUARTER_HOUR_MS } from "../constants";
import type { ChartPoint, NumKey, Row } from "../types";
import type { DeliveryLookup } from "./forecastIndex";

export interface ChartSeries {
  points: ChartPoint[];
  /** The (possibly in-between) time the forecast on screen was made, in ms. The time axis slides with it. */
  forecastTimeMs: number;
  /** One tick per full hour on the time axis. */
  hourTicks: number[];
}

interface ChartSeriesInput {
  origins: string[];
  deliveryRowsAt: DeliveryLookup;
  /** Fractional position in the list of origins: the integer part is a forecast hour, the fraction the time in between. */
  playheadPosition: number;
  actualPrices: Map<string, number>;
}

const toIsoUtc = (ms: number) => new Date(ms).toISOString().slice(0, 19) + "Z";

/** Value of one quantile at a delivery time, blended between two neighbouring forecasts (weight 0 = first, 1 = second). */
function blendQuantile(first: Map<number, Row>, second: Map<number, Row>, deliveryMs: number, quantile: NumKey, weight: number): number | null {
  const a = first.get(deliveryMs);
  const b = second.get(deliveryMs);
  if (a && b) return a[quantile] + (b[quantile] - a[quantile]) * weight;
  const only = b ?? a;
  return only ? only[quantile] : null;
}

/**
 * Smooth chart: the two neighbouring forecasts around the playhead are blended, and so are the forecasts made 3 h earlier.
 * Real prices are split in "known" (already published when the forecast was made) and "later".
 */
export function buildChartSeries({ origins, deliveryRowsAt, playheadPosition, actualPrices }: ChartSeriesInput): ChartSeries {
  const lastIndex = origins.length - 1;
  const position = Math.max(0, Math.min(lastIndex, playheadPosition));
  const earlierIndex = Math.floor(position);
  const laterIndex = Math.min(earlierIndex + 1, lastIndex);
  const weight = position - earlierIndex;
  const originMs = (originPosition: number) => Date.parse(origins[originPosition]);
  const forecastTimeMs = originMs(earlierIndex) + weight * (originMs(laterIndex) - originMs(earlierIndex));

  const earlierForecast = deliveryRowsAt(earlierIndex);
  const laterForecast = deliveryRowsAt(laterIndex);
  const earlierForecastThreeHoursBack = deliveryRowsAt(earlierIndex - 3);
  const laterForecastThreeHoursBack = deliveryRowsAt(laterIndex - 3);

  const knownUntilMs = forecastTimeMs - PUBLICATION_DELAY_MS;
  const lastKnownQuarterMs = Math.floor(knownUntilMs / QUARTER_HOUR_MS) * QUARTER_HOUR_MS;

  const points: ChartPoint[] = [];
  const firstQuarterMs = Math.ceil((forecastTimeMs - 3 * HOUR_MS - QUARTER_HOUR_MS) / QUARTER_HOUR_MS) * QUARTER_HOUR_MS;
  for (let ms = firstQuarterMs; ms <= forecastTimeMs + 10 * HOUR_MS; ms += QUARTER_HOUR_MS) {
    const isFuture = ms >= forecastTimeMs;
    const isPast = ms < forecastTimeMs;
    const p10 = isFuture ? blendQuantile(earlierForecast, laterForecast, ms, "p10", weight) : null;
    const p90 = isFuture ? blendQuantile(earlierForecast, laterForecast, ms, "p90", weight) : null;
    const earlierP10 = isPast ? blendQuantile(earlierForecastThreeHoursBack, laterForecastThreeHoursBack, ms, "p10", weight) : null;
    const earlierP90 = isPast ? blendQuantile(earlierForecastThreeHoursBack, laterForecastThreeHoursBack, ms, "p90", weight) : null;
    const realPrice = actualPrices.get(toIsoUtc(ms)) ?? null;
    const sourceRow = isFuture
      ? (laterForecast.get(ms) ?? earlierForecast.get(ms))
      : (laterForecastThreeHoursBack.get(ms) ?? earlierForecastThreeHoursBack.get(ms));
    points.push({
      ms,
      base: p10,
      width: p10 == null || p90 == null ? null : p90 - p10,
      p10,
      p50: isFuture ? blendQuantile(earlierForecast, laterForecast, ms, "p50", weight) : null,
      p90,
      prevBase: earlierP10,
      prevWidth: earlierP10 == null || earlierP90 == null ? null : earlierP90 - earlierP10,
      prevP50: isPast ? blendQuantile(earlierForecastThreeHoursBack, laterForecastThreeHoursBack, ms, "p50", weight) : null,
      realKnown: ms <= knownUntilMs ? realPrice : null,
      realLater: ms >= lastKnownQuarterMs ? realPrice : null,
      why: sourceRow?.top_drivers ?? "",
    });
  }

  const hourTicks: number[] = [];
  for (let tick = Math.ceil((forecastTimeMs - 3 * HOUR_MS) / HOUR_MS) * HOUR_MS; tick <= forecastTimeMs + 9.75 * HOUR_MS; tick += HOUR_MS) {
    hourTicks.push(tick);
  }
  return { points, forecastTimeMs, hourTicks };
}
