import type { Payload } from "../types";

/** Real imbalance prices by quarter-hour start (UTC ISO text). Empty when the file has no real prices (the test month). */
export function buildActualPriceLookup(payload: Payload): Map<string, number> {
  const prices = new Map<string, number>();
  if (!payload.hasActuals) return prices;
  const deliveryColumn = payload.cols.indexOf("delivery_start_utc");
  const priceColumn = payload.cols.indexOf("actual_imbalance_price");
  for (const row of payload.rows) {
    if (row[priceColumn] != null) prices.set(row[deliveryColumn] as string, row[priceColumn] as number);
  }
  return prices;
}
