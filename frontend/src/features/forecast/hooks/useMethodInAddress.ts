import { useEffect, useState } from "react";
import { isHarnessEnabled } from "@/lib/config";
import type { MethodKey } from "../types";

function methodFromAddress(): MethodKey {
  if (typeof window === "undefined" || !isHarnessEnabled()) return "current";
  return new URLSearchParams(window.location.search).get("method") === "harness" ? "harness" : "current";
}

/**
 * The chosen tab lives in the address (?method=harness). The machine-learning model is the default and leaves the address plain.
 * `initialMethod` comes from the server (so the first paint is right); without it the address is read in the browser.
 */
export function useMethodInAddress(initialMethod?: MethodKey): [MethodKey, (method: MethodKey) => void] {
  const [method, setMethod] = useState<MethodKey>(() => (isHarnessEnabled() ? initialMethod ?? methodFromAddress() : "current"));
  useEffect(() => {
    const url = new URL(window.location.href);
    if (method === "harness") url.searchParams.set("method", "harness");
    else url.searchParams.delete("method");
    window.history.replaceState(null, "", url);
  }, [method]);
  return [method, setMethod];
}
