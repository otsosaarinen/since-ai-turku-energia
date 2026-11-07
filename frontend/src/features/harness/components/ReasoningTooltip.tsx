import type { TooltipProps } from "recharts";
import { finnishDateTime } from "@/lib/finnishTime";
import type { AnswerPoint } from "../types";

/** The little window on hovering a point of the answer chart: the row's numbers and the model's own reasoning (its drivers) for that point. */
export function ReasoningTooltip({ active, payload }: TooltipProps<number, string>) {
  const point = active ? (payload?.[0]?.payload as AnswerPoint | undefined) : undefined;
  if (!point) return null;
  return (
    <div data-testid="harness-tip" className="max-w-72 rounded-md border border-border bg-card p-2 text-xs text-card-foreground shadow-float">
      <div className="font-medium text-foreground">{finnishDateTime(point.ms)}</div>
      <div className="tabular-nums text-muted-foreground">Forecast {point.value.toFixed(1)} €/MWh</div>
      {point.high !== point.low && <div className="tabular-nums text-muted-foreground">Likely range {point.low.toFixed(1)} – {point.high.toFixed(1)} €/MWh</div>}
      {point.confidence && <div className="text-muted-foreground">Confidence {point.confidence}</div>}
      {point.drivers && <div className="mt-1 whitespace-pre-wrap text-muted-foreground">Reasoning: {point.drivers}</div>}
    </div>
  );
}
