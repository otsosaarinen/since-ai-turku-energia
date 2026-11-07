/** Chart colours as references to the theme tokens in app/globals.css, so the chart follows light and dark without a reload.
 *  Values live in the stylesheet only; test/lib/contrast.test.ts checks every one of them against the card background. */
export const CHART_COLORS = {
  grid: "var(--border)",
  axis: "var(--muted-foreground)",
  forecast: "var(--chart-forecast)",
  range: "var(--chart-range)",
  rangeEdge: "var(--chart-range-edge)",
  realPrice: "var(--chart-real)",
  earlierForecast: "var(--chart-earlier)",
  forecastMoment: "var(--foreground)",
} as const;
