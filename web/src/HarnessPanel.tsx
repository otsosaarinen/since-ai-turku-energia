import { useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, cn } from "@/design-system/the-reading-room-3066fa";

// Panel for the "Harness prediction" box: starts a run of harness/harness.py on THIS computer (through the local control server,
// scripts/start_harness.sh, reached via the Vite proxy /harness-api), shows its progress and the answer. On a hosted copy of the website
// (e.g. Vercel) the server does not exist, so the panel only explains how to start it.

const API = "/harness-api";
const SPOT_STEPS = "Follow these steps exactly.";
const PRESETS = [
  {
    label: "Imbalance price, next 12 h",
    prompt:
      `Forecast the Finnish imbalance price for every 2 hours of the next 12 hours (6 rows, starting at the next full hour). ${SPOT_STEPS} ` +
      "1) get_data nordpool_price: take the Finland day-ahead spot price for each of those hours. " +
      "2) get_data fingrid_imbalance_price with start = 5 hours ago and end = now (ISO8601 UTC): you get about 20 quarter-hour prices. " +
      "Pair them with the spot price of the same quarter-hour and compute the spread = imbalance price minus spot, then its median, 10th and 90th percentile with run_python. " +
      "3) Forecast for each hour = spot of that hour + median spread; low = spot + 10th percentile spread; high = spot + 90th percentile spread. " +
      "Do NOT extrapolate a trend line. Clamp all values to -50..400 EUR/MWh. " +
      "4) End with the csv block, horizon=24h, metric=imbalance_price, one row per 2 hours. Keep the explanation under 10 lines.",
  },
  {
    label: "Day-ahead price, next 12 h",
    prompt:
      "Get nordpool_price and list the Finland day-ahead price for every 2 hours of the next 12 hours starting at the next full hour. " +
      "Do not invent any numbers. End with the csv block, horizon=24h, metric=spot_price, low=high=value, drivers=nordpool_price.",
  },
];

interface Info { llama_url: string; models: string[]; max_prompt: number }
export interface JobView { id: string; status: "running" | "done" | "error" | "stopped"; model: string; prompt: string; elapsed: number; lines: string[]; next: number; answer: string }

const solidBtn = "border-2 border-orange-fill bg-orange-fill text-white hover:bg-orange-fill/90";
const outlineBtn = "border-2 border-navy bg-white text-navy hover:bg-bg-light";
const FI = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Helsinki", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

/** Milliseconds for a time written by the model: ISO text (no zone given = UTC) or Unix seconds / milliseconds. NaN if unreadable. */
export function timeMs(t: string): number {
  const s = t.trim();
  if (/^\d{9,10}$/.test(s)) return Number(s) * 1000;
  if (/^\d{12,13}$/.test(s)) return Number(s);
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`).getTime();
}

/** Finnish time (dd/mm/yyyy hh:mm) for a time from the model. */
export function fiTime(t: string): string {
  const ms = timeMs(t);
  if (Number.isNaN(ms)) return t;
  const p = Object.fromEntries(FI.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}`;
}
const hhmm = (ms: number) => fiTime(String(ms)).slice(11);

/** Rows of the first ```csv block of an answer (header + rows), or null. Understands "quoted, fields". */
export function parseCsvBlock(answer: string): { header: string[]; rows: string[][] } | null {
  const m = answer.match(/```csv[ \t]*\n([\s\S]*?)```/);
  if (!m) return null;
  const rows = m[1].trim().split("\n").filter((l) => l.trim()).map((line) => {
    const out: string[] = [];
    let cur = "", q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') { if (q && line[i + 1] === '"') { cur += '"'; i++; } else q = !q; }
      else if (c === "," && !q) { out.push(cur); cur = ""; }
      else cur += c;
    }
    out.push(cur);
    return out.map((x) => x.trim());
  });
  return rows.length ? { header: rows[0], rows: rows.slice(1) } : null;
}

interface Point { ms: number; value: number; base: number; width: number }
/** Points for the answer chart: value with its low-high range, from the time / value / low / high columns. */
export function chartPoints(table: { header: string[]; rows: string[][] }): Point[] {
  const ix = (c: string) => table.header.indexOf(c);
  if (ix("time") < 0 || ix("value") < 0) return [];
  return table.rows.map((r) => {
    const value = Number(r[ix("value")]);
    const low = ix("low") >= 0 && r[ix("low")] !== "" ? Number(r[ix("low")]) : value;
    const high = ix("high") >= 0 && r[ix("high")] !== "" ? Number(r[ix("high")]) : value;
    return { ms: timeMs(r[ix("time")]), value, base: Math.min(low, high, value), width: Math.max(Math.abs(high - low), 0) };
  }).filter((p) => Number.isFinite(p.ms) && Number.isFinite(p.value) && Number.isFinite(p.base) && Number.isFinite(p.width))
    .sort((a, b) => a.ms - b.ms);
}

/** The forecast of an answer as a chart: orange line, blue range. */
function AnswerChart({ points }: { points: Point[] }) {
  return (
    <div className="h-52 min-w-0" data-testid="harness-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis type="number" dataKey="ms" domain={["dataMin", "dataMax"]} tickFormatter={hhmm} stroke="var(--muted-foreground)" fontSize={12} />
          <YAxis stroke="var(--muted-foreground)" fontSize={12} unit=" €" width={52} />
          <Tooltip labelFormatter={(v) => fiTime(String(v))} formatter={(v: number, n: string) => [`${Number(v).toFixed(1)} €/MWh`, n]} />
          <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="width" stackId="b" stroke="none" fill="#46bedc" fillOpacity={0.3} name="Range (low to high)" isAnimationActive={false} />
          <Line dataKey="value" stroke="#c96a00" strokeWidth={3} dot={{ r: 3 }} name="Forecast" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

const stateText = (j: JobView | null) =>
  !j ? "Ready." : j.status === "running" ? `Running … ${Math.round(j.elapsed)} s`
    : j.status === "done" ? `Done in ${Math.round(j.elapsed)} s.` : j.status === "stopped" ? "Stopped." : "Failed. See the progress log.";

export default function HarnessPanel({ pollMs = 1000 }: { pollMs?: number }) {
  const [info, setInfo] = useState<Info | null | "offline">(null);
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [job, setJob] = useState<JobView | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const nextRef = useRef(0);
  const logRef = useRef<HTMLDivElement>(null);
  const running = job?.status === "running";

  const apply = (j: JobView | null) => {
    if (!j) return;
    setJob(j);
    setLines((old) => (nextRef.current === 0 ? j.lines : [...old, ...j.lines]));
    nextRef.current = j.next;
  };

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/info`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((i: Info) => {
        if (cancelled) return;
        setInfo(i);
        setModel((m) => m || i.models.find((x) => /E4B/i.test(x)) || i.models[0] || "");
      }).catch(() => { if (!cancelled) setInfo("offline"); });
    fetch(`${API}/job`).then((r) => (r.ok ? r.json() : null)).then((d) => { if (!cancelled && d && d.job) apply(d.job); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);                                                   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => {
      fetch(`${API}/job?since=${nextRef.current}`).then((r) => r.json()).then((d) => d.job && apply(d.job)).catch(() => setErr("Lost contact with the harness server."));
    }, pollMs);
    return () => clearInterval(id);
  }, [running, pollMs]);                                    // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight; }, [lines.length]);

  const start = () => {
    setErr("");
    fetch(`${API}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, model }) })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || String(r.status)); return d; })
      .then((d) => { nextRef.current = 0; setLines([]); apply(d.job); })
      .catch((e: Error) => setErr(e.message));
  };
  const stop = () => { fetch(`${API}/stop`, { method: "POST" }).catch(() => setErr("Could not stop the run.")); };

  const table = job && job.answer ? parseCsvBlock(job.answer) : null;
  const cols = table ? ["time", "metric", "value", "low", "high", "confidence"].filter((c) => table.header.includes(c)) : [];
  const points = table ? chartPoints(table) : [];
  const text = job && job.answer ? job.answer.replace(/```csv[\s\S]*?```/, "").trim() : "";

  return (
    <Card className="flex flex-1 flex-col gap-3 bg-white p-4 lg:min-h-0 lg:overflow-hidden">
      <h2 className="font-display text-2xl font-bold uppercase tracking-wide">Harness prediction.</h2>
      {info === null && <p className="text-muted-foreground">Looking for the harness server …</p>}
      {info === "offline" && (
        <div className="space-y-2 text-muted-foreground" data-testid="harness-offline">
          <p>The harness runs on your own computer with your local model, so it is not available on this page.</p>
          <p>To use it: open a terminal in the repo folder, run <code>./scripts/start_harness.sh</code>, then reload this page.</p>
        </div>
      )}
      {info && info !== "offline" && (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
          <div className="flex min-h-0 flex-col gap-3">
            <p className="text-sm text-muted-foreground">A live forecast made by an AI model that fetches open data and runs Python. It is not part of the scored submission.</p>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium">Model</span>
              <select aria-label="harness model" className="h-9 rounded-md border border-input bg-white px-3 text-sm" value={model} disabled={running} onChange={(e) => setModel(e.target.value)}>
                {info.models.length === 0 && <option value="">No model found: start the Llama app</option>}
                {info.models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <Button key={p.label} size="sm" variant="outline" className={outlineBtn} disabled={running} onClick={() => setPrompt(p.prompt)}>{p.label}</Button>
              ))}
            </div>
            <label className="flex flex-col gap-1 text-sm lg:min-h-0 lg:flex-1">
              <span className="font-medium">Prompt</span>
              <textarea aria-label="harness prompt" className="h-40 resize-none rounded-md border border-input bg-white p-2 text-sm lg:h-auto lg:min-h-0 lg:flex-1" maxLength={info.max_prompt} value={prompt} disabled={running} onChange={(e) => setPrompt(e.target.value)} />
            </label>
            <div className="flex items-center gap-3">
              <Button size="sm" variant="primary" className={cn(solidBtn, "w-28")} disabled={running || !model || !prompt.trim()} onClick={start}>Start run</Button>
              <Button size="sm" variant="outline" className={cn(outlineBtn, "w-20")} disabled={!running} onClick={stop}>Stop</Button>
              <span className="text-sm text-muted-foreground" data-testid="harness-state">{stateText(job)}</span>
            </div>
            {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          </div>
          <div className="flex min-h-0 flex-col gap-3">
            <div className="flex min-h-0 flex-col lg:flex-1">
              <h3 className="font-display text-base font-bold uppercase tracking-wide">Progress.</h3>
              <div ref={logRef} data-testid="harness-log" className="mt-1 h-64 overflow-auto rounded-md bg-bg-light p-2 font-mono text-xs leading-snug lg:h-auto lg:min-h-0 lg:flex-1">
                {lines.length === 0 ? <span className="text-muted-foreground">Nothing yet. A run takes a few minutes.</span> : lines.map((l, i) => <div key={i} className="break-words">{l}</div>)}
              </div>
            </div>
            {job && job.answer && (
              <div className="lg:max-h-[45%] lg:shrink-0 lg:overflow-auto">
                <h3 className="font-display text-base font-bold uppercase tracking-wide">Answer.</h3>
                {points.length > 1 && <AnswerChart points={points} />}
                {table && cols.length > 0 && (
                  <table className="mt-1 w-full text-left text-sm" data-testid="harness-table">
                    <thead><tr>{cols.map((c) => <th key={c} className="border-b border-grey-light py-1 pr-3 font-medium">{c}</th>)}</tr></thead>
                    <tbody>
                      {table.rows.map((r, i) => (
                        <tr key={i}>{cols.map((c) => { const v = r[table.header.indexOf(c)] ?? ""; return <td key={c} className="py-1 pr-3 tabular-nums">{c === "time" ? fiTime(v) : v}</td>; })}</tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{text}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
