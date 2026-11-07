import type { Payload, Row } from "../../src/features/forecast/types";

/** One forecast row with sensible defaults; override what the test cares about. */
export function makeRow(overrides: Partial<Row> & Pick<Row, "forecast_origin_utc" | "delivery_start_utc">): Row {
  return { step: 1, p10: 10, p50: 20, p90: 30, p_up: 0.5, p_down: 0.5, p_none: 0, p_spike_high: 0.05, p_spike_low: 0.05, ...overrides } as Row;
}

/** A forecast file (columns + rows) from row objects. */
export function makePayload(rows: Row[], hasActuals = false): Payload {
  const cols = Object.keys(rows[0]);
  return { name: "test", hasActuals, cols, rows: rows.map((row) => cols.map((column) => row[column] ?? null)) };
}
