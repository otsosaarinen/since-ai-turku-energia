import { expect, test } from "vitest";
import { buildForecastIndex, createDeliveryLookup } from "../../src/features/forecast/lib/forecastIndex";
import { makePayload, makeRow } from "./helpers";

const payload = makePayload([
  makeRow({ forecast_origin_utc: "2026-10-05T01:00:00Z", delivery_start_utc: "2026-10-05T01:00:00Z" }),
  makeRow({ forecast_origin_utc: "2026-10-05T00:00:00Z", delivery_start_utc: "2026-10-05T00:00:00Z", p50: 42 }),
  makeRow({ forecast_origin_utc: "2026-10-05T00:00:00Z", delivery_start_utc: "2026-10-05T00:15:00Z" }),
]);

test("forecasts are grouped by origin, oldest first", () => {
  const index = buildForecastIndex(payload);
  expect(index.origins).toEqual(["2026-10-05T00:00:00Z", "2026-10-05T01:00:00Z"]);
  expect(index.rowsAt("2026-10-05T00:00:00Z")).toHaveLength(2);
  expect(index.rowsAt("2026-10-05T00:00:00Z")[0].p50).toBe(42);
  expect(index.rowsAt("unknown")).toEqual([]);
});

test("the delivery lookup finds rows by delivery time and is empty outside the list", () => {
  const lookup = createDeliveryLookup(buildForecastIndex(payload));
  expect(lookup(0).get(Date.parse("2026-10-05T00:00:00Z"))?.p50).toBe(42);
  expect(lookup(0)).toBe(lookup(0));   // cached
  expect(lookup(-1).size).toBe(0);
  expect(lookup(2).size).toBe(0);
});
