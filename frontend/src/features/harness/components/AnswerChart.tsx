import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_COLORS } from "@/lib/chartColors";
import { finnishClock } from "@/lib/finnishTime";
import type { AnswerPoint } from "../types";
import { ReasoningTooltip } from "./ReasoningTooltip";

/** The forecast of an answer as a chart: orange line, blue range (same colours as the main chart). */
export function AnswerChart({ points }: { points: AnswerPoint[] }) {
  return (
    <div className="h-52 min-w-0" data-testid="harness-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis type="number" dataKey="ms" domain={["dataMin", "dataMax"]} tickFormatter={finnishClock} stroke={CHART_COLORS.axis} fontSize={12} />
          <YAxis stroke={CHART_COLORS.axis} fontSize={12} unit=" €/MWh" width={76} />
          <Tooltip content={ReasoningTooltip} cursor={{ stroke: CHART_COLORS.axis, strokeDasharray: "3 3" }} />
          <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="width" stackId="b" stroke={CHART_COLORS.rangeEdge} strokeWidth={1} fill={CHART_COLORS.range} fillOpacity={0.28} name="Range (low to high)" isAnimationActive={false} />
          <Line dataKey="value" stroke={CHART_COLORS.forecast} strokeWidth={3} dot={{ r: 3 }} name="Forecast" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
