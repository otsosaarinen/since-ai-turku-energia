import type { Cell, Payload, Row } from "../types";

/** The forecast file grouped by forecast origin (the hour a forecast was made). */
export interface ForecastIndex {
  /** Origins as UTC timestamps, oldest first. */
  origins: string[];
  /** The 40 quarter-hour rows of one origin. */
  rowsAt(origin: string): Row[];
}

export function buildForecastIndex(payload: Payload): ForecastIndex {
  const columnPosition: Record<string, number> = Object.fromEntries(payload.cols.map((column, position) => [column, position]));
  const rowsByOrigin = new Map<string, Cell[][]>();
  for (const cells of payload.rows) {
    const origin = cells[columnPosition.forecast_origin_utc] as string;
    if (!rowsByOrigin.has(origin)) rowsByOrigin.set(origin, []);
    rowsByOrigin.get(origin)!.push(cells);
  }
  const toRow = (cells: Cell[]) => Object.fromEntries(payload.cols.map((column, position) => [column, cells[position]])) as unknown as Row;
  return {
    origins: [...rowsByOrigin.keys()].sort(),
    rowsAt: (origin) => (rowsByOrigin.get(origin) ?? []).map(toRow),
  };
}

/** The rows of the forecast made at origin number `originPosition`, keyed by delivery time in ms. */
export type DeliveryLookup = (originPosition: number) => Map<number, Row>;

const NO_ROWS = new Map<number, Row>();

/** A cached DeliveryLookup: out-of-range positions give an empty map. */
export function createDeliveryLookup(index: ForecastIndex): DeliveryLookup {
  const cache = new Map<number, Map<number, Row>>();
  return (originPosition) => {
    if (originPosition < 0 || originPosition >= index.origins.length) return NO_ROWS;
    let rowsByDelivery = cache.get(originPosition);
    if (!rowsByDelivery) {
      const rows = index.rowsAt(index.origins[originPosition]);
      rowsByDelivery = new Map(rows.map((row) => [Date.parse(row.delivery_start_utc), row]));
      cache.set(originPosition, rowsByDelivery);
    }
    return rowsByDelivery;
  };
}
