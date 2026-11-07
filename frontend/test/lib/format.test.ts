import { expect, test } from "vitest";
import { describeDrivers, formatPercent, formatPrice } from "../../src/features/forecast/lib/format";

test("prices and shares are shown in plain units", () => {
  expect(formatPrice(42.46)).toBe("42.5 €/MWh");
  expect(formatPrice(null)).toBe("–");
  expect(formatPercent(0.234)).toBe("23 %");
});

test("driver groups are explained in plain words, unknown ones are made readable", () => {
  expect(describeDrivers("spot_price;wind_forecast_da")).toBe("the day-ahead price of electricity; the wind power forecast");
  expect(describeDrivers("some_new_group")).toBe("some new group");
  expect(describeDrivers("")).toBe("");
});
