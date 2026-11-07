import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import ForecastViewer from "../src/features/forecast/ForecastViewer";
import { dataUrl, isHarnessEnabled } from "../src/lib/config";

vi.mock("recharts", async (orig) => {
  const m = (await orig()) as Record<string, unknown>;
  return { ...m, ResponsiveContainer: ({ children }: { children: React.ReactElement<{ width?: number; height?: number }> }) => React.cloneElement(children, { width: 600, height: 200 }) };
});

beforeEach(() => {
  global.fetch = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) })) as unknown as typeof fetch;
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); window.history.replaceState(null, "", "/"); });

test("isHarnessEnabled follows NEXT_PUBLIC_HIDE_HARNESS", () => {
  expect(isHarnessEnabled()).toBe(true);
  for (const value of ["true", "1", "TRUE", "True"]) { vi.stubEnv("NEXT_PUBLIC_HIDE_HARNESS", value); expect(isHarnessEnabled()).toBe(false); }
  for (const value of ["false", "0", ""]) { vi.stubEnv("NEXT_PUBLIC_HIDE_HARNESS", value); expect(isHarnessEnabled()).toBe(true); }
});

test("dataUrl uses /data by default and trims a trailing slash from the base", () => {
  expect(dataUrl("validation")).toBe("/data/validation.json");
  expect(dataUrl("variants/index")).toBe("/data/variants/index.json");
  vi.stubEnv("NEXT_PUBLIC_DATA_BASE_URL", "https://example.org/files/");
  expect(dataUrl("final")).toBe("https://example.org/files/final.json");
});

test("with the harness enabled the tab is there", async () => {
  render(<ForecastViewer />);
  expect(await screen.findByRole("button", { name: "Harness prediction" })).toBeTruthy();
});

test("with the harness hidden there is no tab and ?method=harness is ignored", async () => {
  vi.stubEnv("NEXT_PUBLIC_HIDE_HARNESS", "true");
  window.history.replaceState(null, "", "/?method=harness");
  render(<ForecastViewer initialMethod="harness" />);
  await waitFor(() => expect(screen.getByText(/Could not load the forecast/)).toBeTruthy());
  expect(screen.queryByRole("button", { name: "Harness prediction" })).toBeNull();
  expect(screen.queryByText(/harness/i)).toBeNull();
  expect(new URLSearchParams(window.location.search).get("method")).toBeNull();
  expect(screen.getByText(/NEXT_PUBLIC_DATA_BASE_URL/)).toBeTruthy();
});
