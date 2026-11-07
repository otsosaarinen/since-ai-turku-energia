import { vi } from "vitest";
import {
  DEFAULT_COMPUTED_VARIANTS, VARIANT_METRICS, finalPayload, validationPayload,
} from "./forecastData";

type Json = unknown;
export interface MockDataOptions {
  /** File names (without /data/ and .json, e.g. "final" or "variants/validation_011") that answer 404. */
  missing?: string[];
  /** Replace or add files: name -> JSON (or a function, evaluated on every request so a test can change it later). */
  files?: Record<string, Json | (() => Json)>;
  /** Variant keys that exist (default: only "011"). */
  computedVariants?: string[];
  /** Serve the harness_* files (default: 404, as in the real app before the harness has forecasts). */
  harnessReady?: boolean | (() => boolean);
}

const NOT_FOUND = { ok: false, status: 404, json: async () => { throw new Error("404"); } };

/** Serves the fixture files under /data/<name>.json; unknown files give 404. Returns the list of requested URLs. */
export function mockDataFetch(options: MockDataOptions = {}) {
  const requested: string[] = [];
  const computed = new Set(options.computedVariants ?? DEFAULT_COMPUTED_VARIANTS);
  const missing = new Set(options.missing ?? []);
  const lookup = (name: string): Json | undefined => {
    const custom = options.files?.[name];
    if (custom !== undefined) return typeof custom === "function" ? (custom as () => Json)() : custom;
    if (name === "validation") return validationPayload();
    if (name === "final") return finalPayload();
    if (name === "variants/index") return { metrics: VARIANT_METRICS };
    const variant = name.match(/^variants\/(validation|final)_(\d{3})$/);
    if (variant && computed.has(variant[2])) return variant[1] === "validation" ? validationPayload(20, name) : finalPayload(20, name);
    const harness = name.match(/^harness_(validation|final)$/);
    const harnessReady = typeof options.harnessReady === "function" ? options.harnessReady() : options.harnessReady;
    if (harness && harnessReady) return harness[1] === "validation" ? validationPayload(-20, name) : finalPayload(-20, name);
    return undefined;
  };
  global.fetch = vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    requested.push(url);
    const name = url.match(/^\/data\/(.+)\.json$/)?.[1];
    const data = name === undefined || missing.has(name) ? undefined : lookup(name);
    return data === undefined ? NOT_FOUND : { ok: true, status: 200, json: async () => data };
  }) as unknown as typeof fetch;
  return requested;
}
