import { finnishClock, finnishDate } from "@/lib/finnishTime";
import { describeDrivers, formatPrice } from "../lib/format";
import type { ChartPoint } from "../types";

interface ChartTooltipProps {
  active?: boolean;
  payload?: { payload: ChartPoint }[];
}

/** What you see when you point at the chart: the numbers and, in one line, why the forecast is what it is. */
export function ChartTooltip({ active, payload }: ChartTooltipProps) {
  if (!active || !payload || !payload.length) return null;
  const point = payload[0].payload;
  const realPrice = point.realKnown ?? point.realLater;
  return (
    <div className="rounded-md border border-border bg-card p-3 text-sm text-card-foreground shadow-float">
      <p className="font-semibold">{finnishDate(point.ms)} {finnishClock(point.ms)}</p>
      {point.p50 != null && (
        <>
          <p>Forecast: <b>{formatPrice(point.p50)}</b></p>
          <p>Likely range: {formatPrice(point.p10)} to {formatPrice(point.p90)}</p>
        </>
      )}
      {realPrice != null && (
        <p>
          {point.realKnown != null ? "Real price (known at forecast time)" : "Real price (after the forecast)"}: <b>{formatPrice(realPrice)}</b>
        </p>
      )}
      {point.prevP50 != null && <p className="text-muted-foreground">3 h earlier: {formatPrice(point.prevP50)}</p>}
      {point.why && <p className="text-muted-foreground">Why: {describeDrivers(point.why)}</p>}
    </div>
  );
}
