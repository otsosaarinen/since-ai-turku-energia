import { useEffect, useRef, useState } from "react";
import { getJson } from "../lib/api";
import type { JobView, LiveAlert } from "../types";

const ALERT_POLL_INTERVAL_MS = 60_000;

/**
 * The server polls the live feeds itself and starts a run when a new alert appears; this hook only lists the alerts,
 * shows a browser notification for each new one, and picks up a run the server started on its own.
 */
export function useLiveAlerts(options: { isServerReady: boolean; isJobRunning: boolean; onJobStartedByServer: (job: JobView) => void }): LiveAlert[] {
  const { isServerReady, isJobRunning, onJobStartedByServer } = options;
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const isFirstPollRef = useRef(true);
  const isJobRunningRef = useRef(isJobRunning);
  const onJobStartedRef = useRef(onJobStartedByServer);
  useEffect(() => {
    isJobRunningRef.current = isJobRunning;
    onJobStartedRef.current = onJobStartedByServer;
  });

  useEffect(() => {
    if (!isServerReady) return undefined;
    const poll = () => {
      getJson<{ alerts?: LiveAlert[] }>("/alerts")
        .then((data) => {
          const list = data.alerts ?? [];
          setAlerts(list);
          if (!isFirstPollRef.current) {
            list.filter((alert) => !seenIdsRef.current.has(alert.id)).forEach((alert) => {
              if (typeof Notification !== "undefined" && Notification.permission === "granted") {
                new Notification(`Live alert: ${alert.title}`, { body: alert.detail || alert.source });
              }
            });
          }
          isFirstPollRef.current = false;
          list.forEach((alert) => seenIdsRef.current.add(alert.id));
          return getJson<{ job: JobView | null }>("/job");
        })
        .then((data) => {
          if (data?.job?.status === "running" && !isJobRunningRef.current) onJobStartedRef.current(data.job);
        })
        .catch(() => undefined);
    };
    poll();
    const timer = setInterval(poll, ALERT_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isServerReady]);

  return alerts;
}
