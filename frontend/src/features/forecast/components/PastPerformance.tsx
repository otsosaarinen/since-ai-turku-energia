import { Card } from "@/design-system/the-reading-room-3066fa";
import type { PerformanceWindow } from "../lib/pastPerformance";

const NUMBER_CLASS = "font-serif font-normal tabular-nums text-foreground";

/** How the forecasts did before the chosen time: a title and three spans (one row on large screens, stacked on phones). */
export function PastPerformance({ windows }: { windows: PerformanceWindow[] }) {
  return (
    <Card className="order-last flex flex-col gap-2 px-3 py-2.5 lg:order-none lg:flex-row lg:items-center lg:gap-8" data-testid="past-performance">
      <p className="text-sm font-semibold">How the forecast did before this time</p>
      <div className="flex flex-wrap gap-x-8 gap-y-2 lg:flex-1 lg:flex-nowrap">
        {windows.map(({ label, averageError, insideRange }) => (
          <div key={label} className="min-w-44 flex-1 text-sm leading-tight">
            <div className="text-xs text-muted-foreground">{label}</div>
            {averageError == null || insideRange == null ? (
              <div className="text-muted-foreground">No earlier forecasts yet</div>
            ) : (
              <div>
                <b className={NUMBER_CLASS}>{averageError.toFixed(1)}</b> €/MWh off, <b className={NUMBER_CLASS}>{Math.round(insideRange * 100)}%</b> inside range
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
