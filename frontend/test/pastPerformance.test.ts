import { expect, it } from "vitest";
import { pastPerformance } from "@/features/forecast/lib/pastPerformance";
import type { Payload } from "@/features/forecast/types";

const cols = ["forecast_origin_utc", "delivery_start_utc", "p10", "p50", "p90", "actual_imbalance_price"];
const payload = (rows: Payload["rows"], hasActuals = true): Payload => ({ name: "t", hasActuals, cols, rows });

it("returns null without real prices", () => {
  expect(pastPerformance(payload([], false), 0)).toBeNull();
});

it("scores only prices already published and counts the range", () => {
  const rows = [
    ["2026-09-10T00:00:00Z", "2026-09-10T00:00:00Z", 0, 10, 20, 14],   // error 4, inside
    ["2026-09-10T00:00:00Z", "2026-09-10T00:15:00Z", 0, 10, 20, 40],   // error 30, outside
    ["2026-09-10T00:00:00Z", "2026-09-10T09:00:00Z", 0, 10, 20, 15],   // not yet published at "now"
    ["2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", 0, 10, 20, 10],   // older than 7 days
  ];
  const now = Date.parse("2026-09-10T03:00:00Z");
  const [day, week, all] = pastPerformance(payload(rows), now)!;
  expect(day.averageError).toBeCloseTo(17);
  expect(day.insideRange).toBeCloseTo(0.5);
  expect(week.averageError).toBeCloseTo(17);
  expect(all.averageError).toBeCloseTo((4 + 30 + 0) / 3);
});
