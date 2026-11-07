import { useEffect, useState } from "react";
import { dataUrl } from "@/lib/config";
import type { Payload } from "../types";

/**
 * Loads <data base>/<fileName>.json (see dataUrl in lib/config). While a new file loads, the previous data stays on screen (no blink).
 * `error` is set when the file is missing or unreadable.
 */
export function useForecastFile(fileName: string) {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    let isOutdated = false;                      // ignore an answer that arrives after the choice changed again
    setIsLoading(true);                          // eslint-disable-line react-hooks/set-state-in-effect
    setError(null);
    fetch(dataUrl(fileName))
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then((data: Payload) => {
        if (!isOutdated) { setPayload(data); setIsLoading(false); }
      })
      .catch((failure) => {
        if (!isOutdated) { setError(String(failure)); setIsLoading(false); }
      });
    return () => { isOutdated = true; };
  }, [fileName]);
  return { payload, error, isLoading };
}
