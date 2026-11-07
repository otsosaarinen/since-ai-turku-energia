import { expect, test } from "vitest";
import { summarizeOrigin } from "../../src/features/forecast/lib/originSummary";
import { makeRow } from "./helpers";

const row = (quarter: number, overrides = {}) =>
  makeRow({ forecast_origin_utc: "2026-10-05T00:00:00Z", delivery_start_utc: `2026-10-05T0${quarter}:00:00Z`, ...overrides });

test("a calm forecast gives no alerts and an unclear direction", () => {
  const summary = summarizeOrigin([row(1), row(2)], false);
  expect(summary.highAlert).toBeNull();
  expect(summary.lowAlert).toBeNull();
  expect(summary.directionText).toMatch(/unclear/);
  expect(summary.trendRecommendation).toBeNull();
  expect(summary.meanAbsoluteError).toBeNull();
});

test("a spike chance above 20 % is an alert, above 35 % a critical one, with its time window in Finnish time", () => {
  const watch = summarizeOrigin([row(1), row(2, { p_spike_high: 0.25 })], false);
  expect(watch.highAlert?.severity).toBe("HIGH");
  expect(watch.highAlert?.timeWindow).toBe("05:00 – 05:00");   // 02:00 UTC is 05:00 in Finland (summer time)
  expect(watch.highSpikeChip).toEqual({ tone: "high", badge: "High risk" });
  const critical = summarizeOrigin([row(1, { p_spike_low: 0.4 })], false);
  expect(critical.lowAlert?.severity).toBe("CRITICAL");
  expect(critical.lowSpikeText).toBe("40 %");
});

test("the direction follows the share of upward regulation", () => {
  expect(summarizeOrigin([row(1, { p_up: 0.8 })], false).directionText).toMatch(/needs more power/);
  expect(summarizeOrigin([row(1, { p_up: 0.1 })], false).directionText).toMatch(/needs less power/);
});

test("the average error needs real prices", () => {
  const rows = [row(1, { p50: 30, actual_imbalance_price: 40 }), row(2, { p50: 30, actual_imbalance_price: 10 })];
  expect(summarizeOrigin(rows, true).meanAbsoluteError).toBe(15);
  expect(summarizeOrigin(rows, false).meanAbsoluteError).toBeNull();
});
