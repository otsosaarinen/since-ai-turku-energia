// Deployment settings read from NEXT_PUBLIC_* variables. Next inlines them at build time only when they are written
// literally as process.env.NEXT_PUBLIC_NAME, so do not read them through a variable. Functions (not constants) so tests can stub the env.

/** False when NEXT_PUBLIC_HIDE_HARNESS is "true" or "1" (any case): the Harness tab, panel and proxy are then absent. */
export function isHarnessEnabled(): boolean {
  const hide = (process.env.NEXT_PUBLIC_HIDE_HARNESS ?? "").trim().toLowerCase();
  return !(hide === "true" || hide === "1");
}

/** Address of a forecast data file (without the .json ending), e.g. dataUrl("variants/index") -> /data/variants/index.json. */
export function dataUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_DATA_BASE_URL ?? "").trim().replace(/\/+$/, "") || "/data";
  return `${base}/${path}.json`;
}
