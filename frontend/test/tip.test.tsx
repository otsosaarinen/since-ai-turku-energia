import React from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { ChartTooltip } from "../src/features/forecast/components/ChartTooltip";
import type { ChartPoint } from "../src/features/forecast/types";

afterEach(cleanup);

const point: ChartPoint = {
  ms: Date.UTC(2026, 10, 7, 13), base: null, width: null, p10: 10, p50: 42.5, p90: 90,
  prevBase: null, prevWidth: null, prevP50: null, realKnown: null, realLater: null,
  why: "spot_price;wind_forecast_da",
};

test("the hover window on the forecast chart gives the numbers and why the forecast was made", () => {
  const { container } = render(<ChartTooltip active payload={[{ payload: point }]} />);
  const tip = container.textContent!;
  expect(tip).toMatch(/07\/11\/2026 15:00/);                                            // Finnish time
  expect(tip).toMatch(/Forecast: 42.5 €\/MWh/);
  expect(tip).toMatch(/Why: the day-ahead price of electricity; the wind power forecast/);   // driver groups in plain words
  expect(render(<ChartTooltip active={false} payload={[{ payload: point }]} />).container.textContent).toBe("");   // nothing while not hovering
});
