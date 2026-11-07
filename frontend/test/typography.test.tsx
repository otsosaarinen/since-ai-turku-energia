// Brand typography and icon accessibility, checked on the rendered pages.
import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import ForecastViewer from "../src/features/forecast/ForecastViewer";
import HarnessPanel from "../src/features/harness/HarnessPanel";
import { mockDataFetch } from "./fixtures/mockFetch";

vi.mock("recharts", async (orig) => {
  const m = (await orig()) as Record<string, unknown>;
  return { ...m, ResponsiveContainer: ({ children }: { children: React.ReactElement<{ width?: number; height?: number }> }) => React.cloneElement(children, { width: 600, height: 300 }) };
});

afterEach(() => { cleanup(); window.history.replaceState(null, "", "/"); });
beforeEach(() => { global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }; });

const answer = 'Short.\n\n```csv\nhorizon,time,area,metric,value,unit,low,high,confidence,drivers\n24h,2026-11-07T13:00:00+00:00,FI,imbalance_price,42.5,EUR/MWh,10,90,Low,x\n24h,2026-11-07T14:00:00+00:00,FI,imbalance_price,50,EUR/MWh,20,80,Low,y\n```\n';

function expectHeadlinesInBrandStyle() {
  const headings = screen.getAllByRole("heading");
  expect(headings.length).toBeGreaterThan(0);
  for (const heading of headings) {
    const text = heading.textContent ?? "";
    expect(text, `heading "${text}" ends with a full stop`).toMatch(/\.$/);
    expect(heading.className, `heading "${text}" uses the display font in bold capitals`).toMatch(/font-display/);
    expect(heading.className).toMatch(/uppercase/);
    expect(heading.className).toMatch(/font-bold/);
  }
}

function expectIconsAreDecorativeAndButtonsNamed() {
  // all interface icons are decorative; the in-progress spinner is the one icon with a name, and charts are drawn by Recharts
  for (const icon of document.querySelectorAll("svg:not([role='img'])")) {
    if (!icon.closest(".recharts-wrapper")) expect(icon.getAttribute("aria-hidden")).toBe("true");
  }
  const buttons = screen.getAllByRole("button");
  expect(screen.getAllByRole("button", { name: /\S/ })).toHaveLength(buttons.length);                  // every button has an accessible name
}

test("page title and card titles are bold display capitals ending in a full stop; the chart page has named buttons and hidden icons", async () => {
  mockDataFetch();
  render(<ForecastViewer />);
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expectHeadlinesInBrandStyle();
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Imbalance price forecast.");
  expectIconsAreDecorativeAndButtonsNamed();
  expect(screen.getByTestId("when").className).not.toMatch(/font-display/);                            // a time reading is not a headline
});

test("the Harness page headlines (title, Settings, Progress, Forecast) follow the same rule", async () => {
  const ok = (data: unknown) => ({ ok: true, status: 200, json: async () => data });
  global.fetch = vi.fn(async (url: string) => {
    if (url.endsWith("/info")) return ok({ llama_url: "x", models: ["m"], presets: [{ id: "imbalance", label: "Imbalance", about: "a" }], keys: { set: [], missing: [] } });
    if (url.endsWith("/job")) return ok({ job: { id: "a", model: "m", preset: "imbalance", status: "done", elapsed: 9, next: 3, answer, lines: ["[turn 1/10] asking the model", '[tool] run_python {"code":"1"}', "[result] 1 characters: '1'", "[done] final answer received"] } });
    return ok({ job: null });
  }) as unknown as typeof fetch;
  render(<HarnessPanel pollMs={50} />);
  await waitFor(() => expect(screen.getByTestId("harness-chart")).toBeTruthy());
  expect(screen.getAllByRole("heading").map((heading) => heading.textContent)).toEqual(["Harness prediction.", "Settings.", "Progress.", "Forecast."]);
  expectHeadlinesInBrandStyle();
  expectIconsAreDecorativeAndButtonsNamed();
  expect(screen.getByTestId("harness-log").textContent).toMatch(/Done/);                                // the check mark has a text alternative for screen readers
});
