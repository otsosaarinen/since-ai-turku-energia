import { DRIVER_DESCRIPTIONS } from "../constants";

/** "42.5 €/MWh", or a dash when there is no value. */
export function formatPrice(euroPerMwh: number | null | undefined): string {
  return euroPerMwh == null ? "–" : `${euroPerMwh.toFixed(1)} €/MWh`;
}

/** 0.234 -> "23 %" */
export function formatPercent(share: number): string {
  return `${(share * 100).toFixed(0)} %`;
}

/** "spot_price;wind_forecast_da" -> "the day-ahead price of electricity; the wind power forecast" */
export function describeDrivers(driverList: string): string {
  return driverList
    .split(";")
    .filter(Boolean)
    .map((driver) => DRIVER_DESCRIPTIONS[driver] ?? driver.replaceAll("_", " "))
    .join("; ");
}
