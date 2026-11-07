import fs from "node:fs";
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

afterEach(cleanup);   // each test starts with an empty document
import App from "../src/App.jsx";

test("App renders forecast page from data without crashing", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  global.fetch = vi.fn(async (url) => {
    if (!fs.existsSync("public" + url)) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
    return { ok: true, json: async () => JSON.parse(fs.readFileSync("public" + url, "utf8")) };
  });
  render(<App />);
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.getByText(/Main drivers/)).toBeTruthy();
  // switch to the test forecast (no actuals) and back: must not crash
  fireEvent.click(screen.getByText(/Test forecast 5 Oct/));
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.getByText(/Main drivers/)).toBeTruthy();
  expect(screen.queryByText(/hindsight/)).toBeNull();
  // whole-period slider and date box reach the last day of the test period
  const when = () => screen.getByTestId("when").textContent;
  const slider = screen.getByLabelText("whole period");
  fireEvent.change(slider, { target: { value: slider.max } });
  // the controls must keep the same DOM node while the bar is dragged (no remount on every render)
  expect(screen.getByLabelText("whole period")).toBe(slider);
  expect(when()).toMatch(/^01\/11\/2026 23:00$/);
  fireEvent.change(screen.getByLabelText("date"), { target: { value: "2026-10-20" } });
  expect(when()).toMatch(/^20\/10\/2026 00:00$/);
  fireEvent.click(screen.getByText(/Validation 7 Sep/));
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
});

test("two method boxes: the active one is highlighted and switching changes what the chart shows", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  const real = (u) => JSON.parse(fs.readFileSync("public" + u, "utf8"));
  let harnessReady = false;
  global.fetch = vi.fn(async (url) => {
    if (url.includes("harness")) {
      if (!harnessReady) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
      return { ok: true, json: async () => real(url.replace("harness_", "")) };   // pretend the harness files exist
    }
    return { ok: true, json: async () => real(url) };
  });
  render(<App />);
  const current = () => screen.getByRole("button", { name: /Machine-learning model/ });
  const harness = () => screen.getByRole("button", { name: /Harness prediction/ });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(current().getAttribute("aria-pressed")).toBe("true");
  expect(harness().getAttribute("aria-pressed")).toBe("false");

  // harness has no forecasts yet: placeholder instead of the chart, boxes stay
  fireEvent.click(harness());
  await waitFor(() => expect(screen.getByText(/is not connected yet/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.queryByTestId("when")).toBeNull();
  expect(harness().getAttribute("aria-pressed")).toBe("true");
  expect(current().getAttribute("aria-pressed")).toBe("false");
  expect(screen.getByText(/harness_validation\.json/)).toBeTruthy();

  // back to the current model: the chart returns
  fireEvent.click(current());
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });

  // once harness forecasts exist, the same box shows them in the chart
  harnessReady = true;
  fireEvent.click(harness());
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(screen.queryByText(/is not connected yet/)).toBeNull();
  expect(harness().getAttribute("aria-pressed")).toBe("true");
});

test("input toggles switch the chart to the matching precomputed model variant", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  const real = (u) => JSON.parse(fs.readFileSync("public" + u, "utf8"));
  const computed = new Set(["011"]);                                   // pretend only "solar off" has been computed
  const seen = [];
  global.fetch = vi.fn(async (url) => {
    seen.push(url);
    if (url === "/data/variants/index.json") return { ok: true, json: async () => ({ metrics: { "111": { mae: 43.2 }, "011": { mae: 44.0 } } }) };
    const m = url.match(/^\/data\/variants\/(validation|final)_(\d{3})\.json$/);
    if (m) {
      if (!computed.has(m[2])) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
      return { ok: true, json: async () => real(`/data/${m[1]}.json`) };
    }
    if (!fs.existsSync("public" + url)) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
    return { ok: true, json: async () => real(url) };
  });
  render(<App />);
  const sw = (name) => screen.getByRole("switch", { name });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Solar forecast").getAttribute("aria-checked")).toBe("true");
  expect(sw("Wind forecast").getAttribute("aria-checked")).toBe("true");
  expect(sw("Consumption forecast").getAttribute("aria-checked")).toBe("true");
  await waitFor(() => expect(screen.getByTestId("variant-metrics").textContent).toMatch(/43\.2/), { timeout: 15000 });

  // move to a later hour first: flipping a switch must keep that hour and must not blank the page
  const slider = screen.getByLabelText("whole period");
  fireEvent.change(slider, { target: { value: "100" } });
  const hour = screen.getByTestId("when").textContent;
  fireEvent.click(sw("Solar forecast"));                                // solar off -> variant "011"
  expect(screen.queryByText("Loading…")).toBeNull();                    // the chart stays on screen while the variant loads
  expect(screen.getByTestId("when")).toBeTruthy();
  await waitFor(() => expect(seen).toContain("/data/variants/validation_011.json"), { timeout: 15000 });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Solar forecast").getAttribute("aria-checked")).toBe("false");
  expect(screen.getByTestId("when").textContent).toBe(hour);            // same hour as before the switch
  expect(screen.getByTestId("variant-metrics").textContent).toMatch(/44\.0.*\+0\.80 vs all inputs on/);

  fireEvent.click(sw("Wind forecast"));                                 // solar + wind off -> "001" not computed
  await waitFor(() => expect(screen.getByText(/has not been computed yet/)).toBeTruthy(), { timeout: 15000 });
  fireEvent.click(screen.getByRole("button", { name: /Switch all inputs on/ }));
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Wind forecast").getAttribute("aria-checked")).toBe("true");
});

