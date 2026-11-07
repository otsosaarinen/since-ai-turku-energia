import { expect, test } from "vitest";
import { computePriceAxis } from "../../src/features/forecast/lib/priceAxis";
import { makePayload, makeRow } from "./helpers";

const rowWith = (p10: number, p50: number, p90: number) =>
  makeRow({ forecast_origin_utc: "2026-10-05T00:00:00Z", delivery_start_utc: "2026-10-05T00:00:00Z", p10, p50, p90 });

test("the axis is rounded outwards to steps of 50 and always includes zero", () => {
  // 200 forecasts whose upper range climbs from 0 to 199: the 99th percentile is 197, which rounds up to 200
  const rows = Array.from({ length: 200 }, (_, value) => rowWith(value / 10, value / 2, value));
  const axis = computePriceAxis(makePayload(rows));
  expect(axis.lowest).toBe(0);
  expect(axis.highest).toBe(200);
  expect(axis.ticks).toEqual([0, 50, 100, 150, 200]);
});

test("negative prices extend the axis downwards", () => {
  const axis = computePriceAxis(makePayload([rowWith(-120, 10, 60)]));
  expect(axis.lowest).toBe(-150);
});
