import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { finnishClock } from "@/lib/finnishTime";
import { CHART_COLORS } from "@/lib/chartColors";
import { HOUR_MS } from "../constants";
import type { ChartSeries } from "../lib/chartSeries";
import type { PriceAxis } from "../lib/priceAxis";
import { ChartTooltip } from "./ChartTooltip";

// the unit is written once, as a vertical title, not after every tick number (which made two crowded lines per tick)
export const Y_AXIS_TITLE = { value: "€/MWh", angle: -90, position: "insideLeft", fill: "var(--muted-foreground)", fontSize: 12 } as const;

interface ForecastChartProps {
  series: ChartSeries;
  priceAxis: PriceAxis | null;
  hasActuals: boolean;
}

export function ForecastChart({ series, priceAxis, hasActuals }: ForecastChartProps) {
  const { points, forecastTimeMs, hourTicks } = series;
  return (
    <div className="h-80 min-w-0 shrink-0 lg:h-auto lg:flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis type="number" dataKey="ms" domain={[forecastTimeMs - 3 * HOUR_MS, forecastTimeMs + 9.75 * HOUR_MS]} allowDataOverflow ticks={hourTicks} tickFormatter={finnishClock} stroke={CHART_COLORS.axis} fontSize={12} />
          <YAxis domain={priceAxis ? [priceAxis.lowest, priceAxis.highest] : ["auto", "auto"]} ticks={priceAxis ? priceAxis.ticks : undefined} allowDataOverflow stroke={CHART_COLORS.axis} fontSize={12} width={64} label={Y_AXIS_TITLE} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART_COLORS.axis, strokeDasharray: "3 3" }} />
          <Area dataKey="prevBase" stackId="c" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="prevWidth" stackId="c" stroke="none" fill={CHART_COLORS.earlierForecast} fillOpacity={0.15} legendType="none" name="Earlier range" isAnimationActive={false} />
          <Line dataKey="prevP50" stroke={CHART_COLORS.earlierForecast} strokeWidth={2} strokeDasharray="2 3" dot={false} name="Forecast 3 h earlier" isAnimationActive={false} />
          <Area dataKey="base" stackId="b" stroke={CHART_COLORS.rangeEdge} strokeWidth={1} fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="width" stackId="b" stroke={CHART_COLORS.rangeEdge} strokeWidth={1} fill={CHART_COLORS.range} fillOpacity={0.28} name="Likely range" isAnimationActive={false} />
          <Line dataKey="p50" stroke={CHART_COLORS.forecast} strokeWidth={3} dot={false} name="Forecast" isAnimationActive={false} />
          {hasActuals && <Line dataKey="realKnown" stroke={CHART_COLORS.realPrice} strokeWidth={2} dot={false} name="Real price (known)" isAnimationActive={false} />}
          {hasActuals && <Line dataKey="realLater" stroke={CHART_COLORS.realPrice} strokeDasharray="5 3" strokeWidth={2} dot={false} name="Real price (after forecast)" isAnimationActive={false} />}
          <ReferenceLine x={forecastTimeMs} stroke={CHART_COLORS.forecastMoment} strokeWidth={2} label={{ value: "Forecast made", position: "insideTopLeft", fill: "var(--foreground)", fontSize: 12 }} />
          <ReferenceLine y={0} stroke={CHART_COLORS.axis} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--foreground)" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
