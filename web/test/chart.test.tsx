import fs from "node:fs";
import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

// give the chart a real size so Recharts draws it in jsdom (ResponsiveContainer measures 0 x 0 there)
vi.mock("recharts", async (orig) => {
  const m = (await orig()) as Record<string, unknown>;
  return { ...m, ResponsiveContainer: ({ children }: { children: React.ReactElement }) => React.cloneElement(children, { width: 900, height: 400 }) };
});
import App from "../src/App";

afterEach(() => { cleanup(); vi.useRealTimers(); });
beforeEach(() => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  global.fetch = vi.fn(async (url: string) => {
    if (!fs.existsSync("public" + url)) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
    return { ok: true, json: async () => JSON.parse(fs.readFileSync("public" + url, "utf8")) };
  }) as unknown as typeof fetch;
});

const when = () => screen.getByTestId("when").textContent;
const tickLabels = (c: HTMLElement) => [...c.querySelectorAll(".recharts-xAxis .recharts-cartesian-axis-tick-value")].map((n) => n.textContent);
const load = async () => {
  const view = render(<App />);
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  return view;
};

test("the chart draws forecast, range and real price with a sliding hourly time axis", async () => {
  const { container } = await load();
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: "100" } });
  expect(container.querySelectorAll(".recharts-line").length).toBeGreaterThanOrEqual(3);   // forecast, earlier forecast, real price
  expect(container.querySelectorAll(".recharts-area").length).toBeGreaterThanOrEqual(2);   // likely range
  const labels = tickLabels(container);
  expect(labels.length).toBeGreaterThan(8);
  expect(labels.every((t) => /^\d\d:00$/.test(t ?? ""))).toBe(true);                             // one tick per full hour
});

test("a position between two forecast hours slides the axis by part of an hour", async () => {
  const { container } = await load();
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: "100" } });
  const before = container.querySelector(".recharts-xAxis .recharts-cartesian-axis-tick-value")!.getAttribute("x");
  fireEvent.change(slider, { target: { value: "100.5" } });                                // half an hour later
  const after = container.querySelector(".recharts-xAxis .recharts-cartesian-axis-tick-value")!.getAttribute("x");
  expect(before).not.toBe(after);                                                          // the ticks moved a little, not by a whole hour
  expect(Math.abs(+before! - +after!)).toBeGreaterThan(5);
  expect(Math.abs(+before! - +after!)).toBeLessThan(60);
});

test("the 1 h button glides to the next hour instead of jumping", async () => {
  await load();
  const start = when();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: /1 h ▶/ }));
  expect(when()).toBe(start);                                                              // nothing jumps at the click
  act(() => { vi.advanceTimersByTime(33); });
  expect(when()).toBe(start);                                                              // first frame: only a little way there
  act(() => { vi.advanceTimersByTime(1000); });
  expect(when()).not.toBe(start);                                                          // arrived at the next hour
  expect(screen.queryByText("Loading…")).toBeNull();
});

test("Play moves time forward smoothly, Pause stops it", async () => {
  await load();
  const start = when();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "▶ Play" }));
  act(() => { vi.advanceTimersByTime(3500); });
  const played = when();
  expect(played).not.toBe(start);
  fireEvent.click(screen.getByRole("button", { name: "❚❚ Pause" }));
  act(() => { vi.advanceTimersByTime(1500); });                                            // settles on the nearest hour
  const paused = when();
  act(() => { vi.advanceTimersByTime(5000); });
  expect(when()).toBe(paused);                                                             // really stopped
  fireEvent.click(screen.getByRole("button", { name: /Playback speed/ }));
  expect(screen.getByRole("button", { name: /Playback speed 3/ })).toBeTruthy();
});

test("Play stops by itself at the end of the period", async () => {
  await load();
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: String(+slider.max - 2) } });
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "▶ Play" }));
  act(() => { vi.advanceTimersByTime(4000); });
  expect(screen.getByRole("button", { name: "▶ Play" })).toBeTruthy();                       // back to "Play": it stopped at the last hour
  expect(when()).toMatch(/^04\/10\/2026 23:00$/);
});

const priceTicks = (c: HTMLElement) => [...c.querySelectorAll(".recharts-yAxis .recharts-cartesian-axis-tick-value")].map((n) => n.textContent);

test("the price axis stays the same while time moves, even when prices there are very different", async () => {
  const { container } = await load();
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: "10" } });
  const first = priceTicks(container);
  expect(first.length).toBeGreaterThanOrEqual(5);
  expect(first[0]).toBe("-50 €/MWh");
  expect(first[first.length - 1]).toBe("350 €/MWh");
  for (const v of ["10.5", "100", "250", "400", "600"]) {                                  // different hours and in-between positions
    fireEvent.change(slider, { target: { value: v } });
    expect(priceTicks(container)).toEqual(first);
  }
  vi.useFakeTimers();                                                                      // and while playing
  fireEvent.click(screen.getByRole("button", { name: "▶ Play" }));
  for (let i = 0; i < 5; i++) { act(() => { vi.advanceTimersByTime(700); }); expect(priceTicks(container)).toEqual(first); }
});

