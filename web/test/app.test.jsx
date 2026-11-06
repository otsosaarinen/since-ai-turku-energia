import fs from "node:fs";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "../src/App.jsx";

test("App renders forecast page from data without crashing", async () => {
  global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  global.fetch = vi.fn(async (url) => ({ ok: true, json: async () => JSON.parse(fs.readFileSync("public" + url, "utf8")) }));
  render(<App />);
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.getByText(/What drives this forecast/)).toBeTruthy();
  // switch to the test forecast (no actuals) and back: must not crash
  fireEvent.click(screen.getByText(/Test forecast 5 Oct/));
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
  expect(screen.getByText(/What drives this forecast/)).toBeTruthy();
  expect(screen.queryByText(/hindsight/)).toBeNull();
  // whole-period slider and date box reach the last day of the test period
  const when = () => screen.getByTestId("when").textContent;
  const slider = screen.getByLabelText("whole period");
  fireEvent.change(slider, { target: { value: slider.max } });
  expect(when()).toMatch(/^01\.11\. 23:00$/);
  fireEvent.change(screen.getByLabelText("date"), { target: { value: "2026-10-20" } });
  expect(when()).toMatch(/^20\.10\. 00:00$/);
  fireEvent.click(screen.getByText(/Validation 7 Sep/));
  await waitFor(() => expect(screen.getByText(/Summary/)).toBeTruthy(), { timeout: 15000 });
});
