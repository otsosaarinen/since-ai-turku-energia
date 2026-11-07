import { expect, test } from "vitest";
import { buildChartSeries } from "../../src/features/forecast/lib/chartSeries";
import { buildForecastIndex, createDeliveryLookup } from "../../src/features/forecast/lib/forecastIndex";
import { makePayload, makeRow } from "./helpers";

// Two hourly forecasts; each has the same two quarter-hours of delivery, with different p50 so blending is visible.
const origins = ["2026-10-05T00:00:00Z", "2026-10-05T01:00:00Z"];
const rows = origins.flatMap((origin, originNumber) =>
  ["2026-10-05T02:00:00Z", "2026-10-05T02:15:00Z"].map((delivery) => makeRow({ forecast_origin_utc: origin, delivery_start_utc: delivery, p50: originNumber === 0 ? 100 : 200 })),
);
const index = buildForecastIndex(makePayload(rows));
const deliveryRowsAt = createDeliveryLookup(index);
const pointAt = (series: ReturnType<typeof buildChartSeries>, iso: string) => series.points.find((point) => point.ms === Date.parse(iso))!;

test("at a whole position the chart shows that forecast", () => {
  const series = buildChartSeries({ origins: index.origins, deliveryRowsAt, playheadPosition: 0, actualPrices: new Map() });
  expect(series.forecastTimeMs).toBe(Date.parse(origins[0]));
  expect(pointAt(series, "2026-10-05T02:00:00Z").p50).toBe(100);
  expect(pointAt(series, "2026-10-05T00:00:00Z").p50).toBeNull();   // before the forecast was made there is no forecast line
});

test("between two forecasts the chart blends them and the time axis slides", () => {
  const series = buildChartSeries({ origins: index.origins, deliveryRowsAt, playheadPosition: 0.5, actualPrices: new Map() });
  expect(series.forecastTimeMs).toBe(Date.parse("2026-10-05T00:30:00Z"));
  expect(pointAt(series, "2026-10-05T02:00:00Z").p50).toBe(150);
});

test("real prices are split into known at forecast time and published later", () => {
  const actual = new Map([["2026-10-05T00:00:00Z", 55], ["2026-10-05T02:00:00Z", 77]]);
  const series = buildChartSeries({ origins: index.origins, deliveryRowsAt, playheadPosition: 0, actualPrices: actual });
  expect(pointAt(series, "2026-10-05T00:00:00Z")).toMatchObject({ realKnown: null, realLater: 55 });   // forecast made at 00:00: its price is not published yet
  expect(pointAt(series, "2026-10-05T02:00:00Z")).toMatchObject({ realKnown: null, realLater: 77 });
});

test("the time axis has one tick per full hour", () => {
  const series = buildChartSeries({ origins: index.origins, deliveryRowsAt, playheadPosition: 0, actualPrices: new Map() });
  expect(series.hourTicks.every((tick) => tick % (60 * 60 * 1000) === 0)).toBe(true);
  expect(series.hourTicks.length).toBeGreaterThanOrEqual(12);
});
