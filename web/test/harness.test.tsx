import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import HarnessPanel, { chartPoints, fiTime, parseCsvBlock, parseSteps, splitAnswer, timeMs } from "../src/HarnessPanel";

// give the chart a real size so Recharts draws it in jsdom
vi.mock("recharts", async (orig) => {
  const m = (await orig()) as Record<string, unknown>;
  return { ...m, ResponsiveContainer: ({ children }: { children: React.ReactElement }) => React.cloneElement(children, { width: 600, height: 200 }) };
});

afterEach(cleanup);

const answer = 'Short explanation.\n\n```csv\nhorizon,time,area,metric,value,unit,low,high,confidence,drivers\n24h,2026-11-07T13:00:00+00:00,FI,imbalance_price,42.5,EUR/MWh,10,90,Low,"nordpool_price, fingrid"\n24h,1794002400,FI,imbalance_price,50,EUR/MWh,20,80,Low,x\n```\n';

test("parseCsvBlock reads the table, including quoted commas", () => {
  const t = parseCsvBlock(answer)!;
  expect(t.header[1]).toBe("time");
  expect(t.rows).toHaveLength(2);
  expect(t.rows[0][9]).toBe("nordpool_price, fingrid");
  expect(parseCsvBlock("no table here")).toBeNull();
});

test("the panel says how to start the server when it is not running", async () => {
  global.fetch = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) })) as unknown as typeof fetch;
  render(<HarnessPanel pollMs={10} />);
  await waitFor(() => expect(screen.getByTestId("harness-offline")).toBeTruthy());
  expect(screen.getByText(/start_harness\.sh/)).toBeTruthy();
});

test("start a run, watch the progress, see the answer table", async () => {
  let polls = 0;
  const calls: { url: string; body?: string }[] = [];
  const base = { id: "a1", model: "ggml-org/gemma-4-E4B-it-GGUF:Q8_0", preset: "imbalance" };
  global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body as string | undefined });
    const ok = (data: unknown) => ({ ok: true, status: 200, json: async () => data });
    if (url.endsWith("/info")) return ok({ llama_url: "x", models: ["ggml-org/gemma-4-12B-it-GGUF:Q8_0", "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"], presets: [{ id: "imbalance", label: "Imbalance price, next 12 h", about: "About imbalance." }, { id: "dayahead", label: "Day-ahead price, next 12 h", about: "About day-ahead." }] });
    if (url.endsWith("/job")) return ok({ job: null });
    if (url.endsWith("/run")) return ok({ job: { ...base, status: "running", elapsed: 0, lines: ["[start] model", "[turn 1/10] asking the model"], next: 2, answer: "" } });
    if (url.includes("/job?since=")) {
      polls++;
      if (polls < 2) return ok({ job: { ...base, status: "running", elapsed: 3, lines: ["[tool] get_data {\"source\":\"nordpool_price\"}"], next: 3, answer: "" } });
      return ok({ job: { ...base, status: "done", elapsed: 9, lines: ["[turn 2/10] asking the model", "[done] final answer received"], next: 5, answer } });
    }
    return ok({});
  }) as unknown as typeof fetch;

  render(<HarnessPanel pollMs={10} />);
  const select = (await screen.findByLabelText("harness model")) as HTMLSelectElement;
  await waitFor(() => expect(select.value).toMatch(/E4B/));                       // the small fast model is the default
  expect(screen.queryByLabelText("harness prompt")).toBeNull();                   // the prompt cannot be edited
  fireEvent.click(screen.getByRole("button", { name: "Day-ahead price, next 12 h" }));
  expect(screen.getByTestId("harness-about").textContent).toMatch(/About day-ahead/);
  fireEvent.click(screen.getByRole("button", { name: "Start run" }));
  await waitFor(() => expect(screen.getByTestId("harness-log").textContent).toMatch(/Fetching nordpool_price/));
  await waitFor(() => expect(screen.getByTestId("harness-table")).toBeTruthy());
  expect(screen.getByTestId("harness-log").textContent).toMatch(/Step 1: Fetching nordpool_price.*Step 2: Writing the answer/);   // steps in order
  expect(screen.getByTestId("harness-state").textContent).toMatch(/Done in 9 s/);
  expect(screen.getByTestId("harness-table").textContent).toMatch(/07\/11\/2026 15:00/);          // shown in Finnish time
  expect(screen.getByTestId("harness-chart").querySelectorAll(".recharts-line").length).toBeGreaterThan(0);   // and drawn as a chart
  const run = calls.find((c) => c.url.endsWith("/run"))!;
  expect(JSON.parse(run.body!).model).toMatch(/E4B/);
  expect(JSON.parse(run.body!)).toEqual({ preset: "dayahead", model: "ggml-org/gemma-4-E4B-it-GGUF:Q8_0" });   // only a preset name is sent, never text
});

test("times from the model: ISO, no zone, Unix seconds; chart points sorted with a range", () => {
  expect(timeMs("2026-11-07T13:00:00Z")).toBe(Date.UTC(2026, 10, 7, 13));
  expect(timeMs("2026-11-07T13:00:00")).toBe(Date.UTC(2026, 10, 7, 13));          // no zone = UTC
  expect(timeMs("1793998800")).toBe(1793998800000);                              // Unix seconds
  expect(fiTime("2026-11-07T13:00:00Z")).toBe("07/11/2026 15:00");               // Finnish time
  const pts = chartPoints(parseCsvBlock(answer)!);
  expect(pts).toHaveLength(2);
  expect(pts[0].ms).toBeLessThan(pts[1].ms);
  expect(pts[0]).toMatchObject({ value: 50, base: 20, width: 60 });            // the Unix-seconds row is earlier
  expect(pts[1]).toMatchObject({ value: 42.5, base: 10, width: 80 });
});

test("a table without a code fence is found too (small models skip it)", () => {
  const plain = "Done.\nhorizon,time,area,metric,value,unit,low,high,confidence,drivers\n24h,2026-11-07T13:00:00Z,FI,spot_price,29.99,EUR/MWh,29.99,29.99,High,x\n24h,2026-11-07T15:00:00Z,FI,spot_price,24.4,EUR/MWh,24.4,24.4,High,x\n\nBye.";
  const t = parseCsvBlock(plain)!;
  expect(t.rows).toHaveLength(2);
  expect(splitAnswer(plain).text).toBe("Done.\n\nBye.");
  expect(chartPoints(t)).toHaveLength(2);
  const other = "```\ntime,value\n2026-11-07T13:00:00Z,5\n2026-11-07T14:00:00Z,6\n```";
  expect(parseCsvBlock(other)!.rows).toHaveLength(2);
  expect(parseCsvBlock("Just words, with a comma.")).toBeNull();
});

test("an older server without presets does not blank the page", async () => {
  global.fetch = vi.fn(async (url: string) => ({
    ok: true, status: 200,
    json: async () => (url.endsWith("/info") ? { llama_url: "x", models: ["m"], max_prompt: 4000 } : { job: null }),
  })) as unknown as typeof fetch;
  render(<HarnessPanel pollMs={10} />);
  await waitFor(() => expect(screen.getByTestId("harness-outdated")).toBeTruthy());
  expect(screen.getByText(/start_harness\.sh/)).toBeTruthy();
});

test("progress lines become a list of steps: finished ones struck through, the current one with a spinner", () => {
  const lines = [
    "[start] model m",
    "[turn 1/10] asking the model",
    '[tool] get_data {"params":{"start":"5 hours ago"},"source":"fingrid_imbalance_price"}',
    "[result] 136 characters: \"Error: URL can't contain control characters\"",
    "[turn 2/10] asking the model",
    '[tool] run_python {"code":"print(1)"}',
    "[result] 3 characters: '391'",
    "[turn 3/10] asking the model",
  ];
  const running = parseSteps(lines, "running");
  expect(running.map((s) => s.title)).toEqual(["Fetching fingrid_imbalance_price", "Running Python", "Asking the model"]);
  expect(running.map((s) => s.state)).toEqual(["done", "done", "active"]);
  expect(running[0].detail).toMatch(/^failed: Error/);
  expect(running[1].detail).toBe("3 characters received");
  const done = parseSteps([...lines, "[done] final answer received"], "done");
  expect(done[2]).toMatchObject({ title: "Writing the answer", state: "done" });
  expect(parseSteps(lines, "stopped")[2].state).toBe("failed");
  expect(parseSteps([], "running")).toEqual([]);
});

test("while running the current step has a spinner and finished steps are struck through", async () => {
  global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => ({ ok: true, status: 200, json: async () => data });
    if (url.endsWith("/info")) return ok({ llama_url: "x", models: ["ggml-org/gemma-4-E4B-it-GGUF:Q8_0"], presets: [{ id: "imbalance", label: "I", about: "a" }] });
    if (url.endsWith("/job")) return ok({ job: { id: "a", model: "m", preset: "imbalance", status: "running", elapsed: 5, next: 4, answer: "",
      lines: ["[turn 1/10] asking the model", '[tool] run_python {"code":"1"}', "[result] 1 characters: '1'", "[turn 2/10] asking the model"] } });
    return ok({ job: null });
  }) as unknown as typeof fetch;
  render(<HarnessPanel pollMs={50} />);
  await waitFor(() => expect(screen.getByTestId("harness-log").querySelectorAll("li").length).toBe(2));
  const items = screen.getByTestId("harness-log").querySelectorAll("li");
  expect(items[0].className).toMatch(/line-through/);
  expect(items[0].getAttribute("data-state")).toBe("done");
  expect(items[1].getAttribute("data-state")).toBe("active");
  expect(items[1].querySelector("svg.animate-spin")).toBeTruthy();
});
