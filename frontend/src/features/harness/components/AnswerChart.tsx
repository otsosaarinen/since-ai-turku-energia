import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_COLORS } from "@/lib/chartColors";
import { finnishClock, finnishDate } from "@/lib/finnishTime";
import type { AnswerPoint } from "../types";
import { Y_AXIS_TITLE } from "@/features/forecast/components/ForecastChart";
import { ReasoningTooltip } from "./ReasoningTooltip";

const ONE_AND_A_HALF_DAYS_MS = 36 * 60 * 60 * 1000;

/** Tick text for the time axis: the clock for a short answer, day and clock when it spans days (otherwise the labels look out of order). */
export function answerTickFormatter(points: AnswerPoint[]): (ms: number) => string {
  const span = points.length ? points[points.length - 1].ms - points[0].ms : 0;
  return span > ONE_AND_A_HALF_DAYS_MS ? (ms) => `${finnishDate(ms).slice(0, 5)} ${finnishClock(ms)}` : finnishClock;
}

const MAX_LABELLED_POINTS = 12;

/** With a few points every point gets its own label (otherwise the axis invents times like 06:10); with many, the axis chooses. */
export function tickPositions(points: AnswerPoint[]): number[] | undefined {
  return points.length <= MAX_LABELLED_POINTS ? points.map((point) => point.ms) : undefined;
}

/** The forecast of an answer as a chart: orange line, blue range (same colours as the main chart). */
export function AnswerChart({ points }: { points: AnswerPoint[] }) {
  return (
    <div className="h-52 min-w-0" data-testid="harness-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis type="number" dataKey="ms" domain={["dataMin", "dataMax"]} ticks={tickPositions(points)} tickFormatter={answerTickFormatter(points)} stroke={CHART_COLORS.axis} fontSize={12} />
          <YAxis stroke={CHART_COLORS.axis} fontSize={12} width={64} label={Y_AXIS_TITLE} />
          <Tooltip content={ReasoningTooltip} cursor={{ stroke: CHART_COLORS.axis, strokeDasharray: "3 3" }} />
          <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="width" stackId="b" stroke={CHART_COLORS.rangeEdge} strokeWidth={1} fill={CHART_COLORS.range} fillOpacity={0.28} name="Range (low to high)" isAnimationActive={false} />
          <Line dataKey="value" stroke={CHART_COLORS.forecast} strokeWidth={3} dot={{ r: 3 }} name="Forecast" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
