import type { Payload, Row } from "../../src/features/forecast/types";
import { makePayload, makeRow } from "../lib/helpers";

/** Deterministic stand-ins for the forecast files of the git-ignored real forecast files (tests must never read those). */
const HOUR = 3_600_000;
const QUARTER = 900_000;
const STEPS = 40;

// Last origins are 23:00 Finnish time (the viewer shows Finnish time).
export const VALIDATION_FIRST_ORIGIN = "2026-09-07T00:00:00Z";
export const VALIDATION_LAST_ORIGIN = "2026-10-04T20:00:00Z";
export const FINAL_FIRST_ORIGIN = "2026-10-05T00:00:00Z";
export const FINAL_LAST_ORIGIN = "2026-11-01T21:00:00Z";

/** Validation error shown for each variant key by the input switches. */
export const VARIANT_METRICS: Record<string, { mae: number }> = { "111": { mae: 43.2 }, "011": { mae: 44.0 } };
/** Variant keys that have a forecast file by default (the others answer 404, like variants not yet computed). */
export const DEFAULT_COMPUTED_VARIANTS = ["011"];

const iso = (ms: number) => new Date(ms).toISOString().replace(".000Z", "Z");

function makeRows(firstOrigin: string, lastOrigin: string, withActuals: boolean, shift: number): Row[] {
  const rows: Row[] = [];
  for (let origin = Date.parse(firstOrigin); origin <= Date.parse(lastOrigin); origin += HOUR) {
    for (let step = 1; step <= STEPS; step++) {
      const delivery = origin + HOUR + (step - 1) * QUARTER;
      const wave = Math.sin(delivery / (6 * HOUR));
      const p50 = 60 + shift + 40 * wave;
      const spike = Math.max(0, Math.sin(delivery / (31 * HOUR)));
      rows.push(makeRow({
        forecast_origin_utc: iso(origin), delivery_start_utc: iso(delivery), step,
        p10: p50 - 70, p50, p90: p50 + 90 + 30 * Math.abs(wave),
        p_up: 0.4 + 0.2 * wave, p_down: 0.4 - 0.2 * wave, p_none: 0.2,
        p_spike_high: 0.05 + 0.3 * spike, p_spike_low: 0.05,
        top_drivers: "spot_price 40%; calendar 30%; wind_forecast_da 30%",
        ...(withActuals ? { actual_imbalance_price: p50 + 25 * Math.cos(delivery / (2 * HOUR)) } : {}),
      }));
    }
  }
  return rows;
}

const cache = new Map<string, Payload>();
function build(name: string, first: string, last: string, withActuals: boolean, shift: number): Payload {
  let payload = cache.get(name);
  if (!payload) {
    payload = { ...makePayload(makeRows(first, last, withActuals, shift), withActuals), name };
    cache.set(name, payload);
  }
  return payload;
}

/** Validation month: hourly origins, 40 quarter-hours each, real prices present. */
export const validationPayload = (shift = 0, name = "validation"): Payload => build(name, VALIDATION_FIRST_ORIGIN, VALIDATION_LAST_ORIGIN, true, shift);
/** Test month: same shape, no real prices. */
export const finalPayload = (shift = 0, name = "final"): Payload => build(name, FINAL_FIRST_ORIGIN, FINAL_LAST_ORIGIN, false, shift);
