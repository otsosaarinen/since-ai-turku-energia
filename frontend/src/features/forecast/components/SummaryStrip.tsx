import { Card, cn } from "@/design-system/the-reading-room-3066fa";
import { StatChip } from "./StatChip";
import type { OriginSummary } from "../lib/originSummary";

interface SummaryStripProps {
  summary: OriginSummary;
  hasActuals: boolean;
}

const RECOMMENDATION_BOX = "flex items-center gap-1 rounded-sm px-2 py-0.5";

/** One slim strip: what the forecast means, the operational hints, and the key numbers. */
export function SummaryStrip({ summary, hasActuals }: SummaryStripProps) {
  const { highAlert, lowAlert } = summary;
  return (
    <Card className="order-last flex flex-wrap items-center gap-x-6 gap-y-3 border-l-4 border-l-brand p-3 lg:order-none lg:flex-nowrap lg:overflow-visible">
      <div className="min-w-64 flex-1 lg:min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="leading-snug lg:line-clamp-1" title={summary.directionText}>{summary.directionText}</p>
        </div>

        {/* Operational recommendations for shift supervisors */}
        {(highAlert || lowAlert) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
            {highAlert && (
              <div className={cn(RECOMMENDATION_BOX, highAlert.severity === "CRITICAL" ? "bg-destructive-soft text-destructive" : "bg-accent text-accent-foreground")}>
                <span className="font-semibold">{highAlert.timeWindow}:</span>
                <span>{highAlert.recommendation}</span>
              </div>
            )}
            {lowAlert && (
              <div className={cn(RECOMMENDATION_BOX, "bg-bg-light text-navy")}>
                <span className="font-semibold">{lowAlert.timeWindow}:</span>
                <span>{lowAlert.recommendation}</span>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <StatChip value={summary.highSpikeText} label="high price spike" tone={summary.highSpikeChip.tone} badge={summary.highSpikeChip.badge} />
        <StatChip value={summary.lowSpikeText} label="low price spike" tone={summary.lowSpikeChip.tone} badge={summary.lowSpikeChip.badge} />
        {hasActuals && <StatChip value={summary.meanAbsoluteError == null ? "–" : summary.meanAbsoluteError.toFixed(1)} label={"average error\n€/MWh"} />}
      </div>
    </Card>
  );
}
