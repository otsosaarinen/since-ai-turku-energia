import { Button, cn } from "@/design-system/the-reading-room-3066fa";
import { formatModelTime } from "../lib/modelTime";
import type { LiveAlert } from "../types";

const URGENT_SEVERITIES = ["red", "orange", "high"];

/** Live alerts from the feeds. A new one makes the server recalculate the forecast. */
export function LiveAlertsList({ alerts }: { alerts: LiveAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <div className="flex flex-col gap-1 text-xs" data-testid="live-alerts">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">Live alerts</span>
        <span className="text-muted-foreground">{alerts.length} · a new one recalculates the forecast automatically</span>
        {typeof Notification !== "undefined" && Notification.permission === "default" && (
          <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={() => Notification.requestPermission()}>Notify</Button>
        )}
      </div>
      <ul className="max-h-40 space-y-1 overflow-auto">
        {alerts.map((alert) => (
          <li key={alert.id} className={cn("rounded-sm border px-2 py-1", URGENT_SEVERITIES.includes(alert.severity) ? "border-destructive bg-destructive-soft text-destructive" : "border-border")}>
            <span className="font-medium">{alert.title}</span>{" "}
            <span className="text-muted-foreground">· {alert.source}{alert.until ? `, until ${formatModelTime(alert.until)}` : ""}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
