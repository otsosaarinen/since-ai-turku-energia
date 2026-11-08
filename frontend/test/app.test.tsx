import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

afterEach(() => { cleanup(); window.history.replaceState(null, "", "/"); });   // each test starts with an empty document and a plain address
import ForecastViewer from "../src/features/forecast/ForecastViewer";
import { VARIANT_METRICS } from "./fixtures/forecastData";
import { mockDataFetch } from "./fixtures/mockFetch";

test("App renders forecast page from data without crashing", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  mockDataFetch();
  render(<ForecastViewer />);
  await waitFor(() => expect(screen.getByText(/high price spike/)).toBeTruthy(), { timeout: 15000 });
  // switch to the test forecast (no actuals) and back: must not crash
  fireEvent.click(screen.getByText(/Test forecast 5 Oct/));
  const when = () => screen.getByTestId("when").textContent;
  await waitFor(() => expect(when()).toMatch(/^05\/10\/2026/), { timeout: 15000 });   // the test file has loaded (the old chart stays on screen until then)
  expect(screen.queryByText(/hindsight/)).toBeNull();
  // whole-period slider and date box reach the last day of the test period
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: slider.max } });
  // the controls must keep the same DOM node while the bar is dragged (no remount on every render)
  expect(screen.getByLabelText("whole period")).toBe(slider);
  expect(when()).toMatch(/^01\/11\/2026 23:00$/);
  fireEvent.change(screen.getByLabelText("date"), { target: { value: "2026-10-20" } });
  expect(when()).toMatch(/^20\/10\/2026 00:00$/);
  fireEvent.click(screen.getByText(/Validation 7 Sep/));
  await waitFor(() => expect(screen.getByText(/high price spike/)).toBeTruthy(), { timeout: 15000 });
});

test("two method boxes: the active one is highlighted and switching changes what the chart shows", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  let harnessReady = false;
  mockDataFetch({ harnessReady: () => harnessReady });   // harness files 404 until the test pretends they exist
  render(<ForecastViewer />);
  const current = () => screen.getByRole("button", { name: /Machine-learning model/ });
  const harness = () => screen.getByRole("button", { name: /Harness prediction/ });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(current().getAttribute("aria-pressed")).toBe("true");
  expect(harness().getAttribute("aria-pressed")).toBe("false");

  // harness has no forecast files yet: the harness panel (here: server not running) instead of the chart, boxes stay
  fireEvent.click(harness());
  await waitFor(() => expect(screen.getByTestId("harness-offline")).toBeTruthy(), { timeout: 15000 });
  expect(screen.queryByTestId("when")).toBeNull();
  expect(harness().getAttribute("aria-pressed")).toBe("true");
  expect(current().getAttribute("aria-pressed")).toBe("false");
  expect(screen.getByText(/\.\/dev\.sh/)).toBeTruthy();

  // back to the current model: the chart returns
  fireEvent.click(current());
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });

  // once harness forecasts exist, the same box shows them in the chart
  harnessReady = true;
  fireEvent.click(harness());
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(screen.queryByTestId("harness-offline")).toBeNull();
  expect(harness().getAttribute("aria-pressed")).toBe("true");
});

test("input toggles switch the chart to the matching precomputed model variant", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  const seen = mockDataFetch({ computedVariants: ["011"] });   // pretend only "solar off" has been computed
  render(<ForecastViewer />);
  const sw = (name: string) => screen.getByRole("switch", { name });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Solar forecast").getAttribute("aria-checked")).toBe("true");
  expect(sw("Wind forecast").getAttribute("aria-checked")).toBe("true");
  expect(sw("Consumption forecast").getAttribute("aria-checked")).toBe("true");
  await waitFor(() => expect(screen.getByTestId("variant-metrics").textContent).toMatch(new RegExp(VARIANT_METRICS["111"].mae.toFixed(1))), { timeout: 15000 });

  // move to a later hour first: flipping a switch must keep that hour and must not blank the page
  const slider = screen.getByLabelText("whole period") as HTMLInputElement;
  fireEvent.change(slider, { target: { value: "100" } });
  const hour = screen.getByTestId("when").textContent;
  fireEvent.click(sw("Solar forecast"));                                // solar off -> variant "011"
  expect(screen.queryByText("Loading…")).toBeNull();                    // the chart stays on screen while the variant loads
  expect(screen.getByTestId("when")).toBeTruthy();
  await waitFor(() => expect(seen).toContain("/data/variants/validation_011.json"), { timeout: 15000 });
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Solar forecast").getAttribute("aria-checked")).toBe("false");
  expect(screen.getByTestId("when").textContent).toBe(hour);            // same hour as before the switch
  expect(screen.getByTestId("variant-metrics").textContent).toMatch(new RegExp(VARIANT_METRICS["011"].mae.toFixed(1) + ".*\\+" + (VARIANT_METRICS["011"].mae - VARIANT_METRICS["111"].mae).toFixed(2).replace(".", "\\.")));

  fireEvent.click(sw("Wind forecast"));                                 // solar + wind off -> "001" not computed
  await waitFor(() => expect(screen.getByText(/has not been computed yet/)).toBeTruthy(), { timeout: 15000 });
  fireEvent.click(screen.getByRole("button", { name: /Switch all inputs on/ }));
  await waitFor(() => expect(screen.getByTestId("when")).toBeTruthy(), { timeout: 15000 });
  expect(sw("Wind forecast").getAttribute("aria-checked")).toBe("true");
});


test("the chosen tab is shown in the address and read back from it", async () => {
  mockDataFetch({ missing: ["validation", "final", "harness_validation", "harness_final"] });   // nothing to load
  window.history.replaceState(null, "", "/?method=harness");
  render(<ForecastViewer />);
  expect(screen.getByRole("button", { name: /Harness prediction/ }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: /Machine-learning model/ }));
  expect(window.location.search).toBe("");
  fireEvent.click(screen.getByRole("button", { name: /Harness prediction/ }));
  expect(window.location.search).toBe("?method=harness");
});

test("the explanation is hidden until 'How to use' is clicked, and closes again", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  mockDataFetch();
  render(<ForecastViewer />);
  await waitFor(() => expect(screen.getByText(/high price spike/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "How to use" }));
  expect(screen.getByRole("dialog").textContent).toMatch(/Press Play/);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("on phones the period and input controls open from a Settings button", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  mockDataFetch();
  render(<ForecastViewer />);
  await waitFor(() => expect(screen.getByText(/high price spike/)).toBeTruthy(), { timeout: 15000 });
  fireEvent.click(screen.getByRole("button", { name: /Settings: period and inputs/ }));
  const dialog = screen.getByRole("dialog");
  expect(dialog.textContent).toMatch(/Forecast inputs/);
  expect(dialog.textContent).toMatch(/Test forecast 5 Oct/);
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
});
