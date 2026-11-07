import type { Payload } from "../types";

export interface PriceAxis {
  lowest: number;
  highest: number;
  ticks: number[];
}

const AXIS_STEP = 50;   // EUR/MWh

function sortedColumn(payload: Payload, column: string): number[] {
  const position = payload.cols.indexOf(column);
  if (position < 0) return [];
  return (payload.rows.map((row) => row[position]).filter((value) => value != null) as number[]).sort((a, b) => a - b);
}

function percentile(sortedValues: number[], share: number): number | null {
  if (!sortedValues.length) return null;
  return sortedValues[Math.min(sortedValues.length - 1, Math.floor(share * (sortedValues.length - 1)))];
}

/**
 * Fixed price axis for the whole period, so the numbers on the left never move while time moves or plays.
 * From the 1st percentile of the low end to the 99.9th percentile of the forecast line, the 99th percentile of the high end of the
 * likely range and the 97th for real prices, rounded outwards to steps of 50 EUR/MWh. Rare larger values run off the chart
 * (the hover window still shows them).
 */
export function computePriceAxis(payload: Payload): PriceAxis {
  const realPrices = sortedColumn(payload, "actual_imbalance_price");
  const lowCandidates = [percentile(sortedColumn(payload, "p10"), 0.01), percentile(realPrices, 0.01)].filter((value): value is number => value != null);
  const highCandidates = [
    percentile(sortedColumn(payload, "p50"), 0.999),
    percentile(sortedColumn(payload, "p90"), 0.99),
    percentile(realPrices, 0.97),
  ].filter((value): value is number => value != null);
  const lowest = Math.min(0, Math.floor(Math.min(...lowCandidates) / AXIS_STEP) * AXIS_STEP);
  const highest = Math.max(AXIS_STEP, Math.ceil(Math.max(...highCandidates) / AXIS_STEP) * AXIS_STEP);
  const ticks: number[] = [];
  for (let tick = lowest; tick <= highest; tick += AXIS_STEP) ticks.push(tick);
  return { lowest, highest, ticks };
}
