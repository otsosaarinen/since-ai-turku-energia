import { useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { Button, Card, cn } from "@/design-system/the-reading-room-3066fa";

// Panel for the "Harness prediction" box: starts a run of harness/harness.py on THIS computer (through the local control server,
// scripts/start_harness.sh, reached via the Vite proxy /harness-api), shows its progress and the answer. On a hosted copy of the website
// (e.g. Vercel) the server does not exist, so the panel only explains how to start it.

const API = "/harness-api";
interface Preset { id: string; label: string; about: string }
interface Keys { set: string[]; missing: string[] }
interface Info { llama_url: string; models: string[]; presets: Preset[]; keys?: Keys }
export interface JobView { id: string; status: "running" | "done" | "error" | "stopped"; model: string; preset: string; elapsed: number; lines: string[]; next: number; answer: string }

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

/** Where the table is in an answer: a ```csv block, any code block that starts like a table, or plain comma-separated lines (small models often skip the fence). */
export function splitAnswer(answer: string): { csv: string | null; text: string } {
  const m = answer.match(/```csv[ \t]*\n([\s\S]*?)```/);
  if (m) return { csv: m[1], text: answer.replace(m[0], "").trim() };
  for (const f of answer.matchAll(/```[a-z]*[ \t]*\n([\s\S]*?)```/g)) {
    const first = f[1].trim().split("\n")[0].toLowerCase();
    if (first.includes("time") && first.includes("value")) return { csv: f[1], text: answer.replace(f[0], "").trim() };
  }
  const lines = answer.split("\n");
  const start = lines.findIndex((l) => l.includes(",") && /(^|,)\s*time\s*(,|$)/i.test(l) && /(^|,)\s*value\s*(,|$)/i.test(l));
  if (start < 0) return { csv: null, text: answer.trim() };
  let end = start + 1;
  while (end < lines.length && lines[end].includes(",")) end++;
  return { csv: lines.slice(start, end).join("\n"), text: [...lines.slice(0, start), ...lines.slice(end)].join("\n").trim() };
}

/** Rows of the table in an answer (header + rows), or null. Understands "quoted, fields". */
export function parseCsvBlock(answer: string): { header: string[]; rows: string[][] } | null {
  const { csv } = splitAnswer(answer);
  if (!csv) return null;
  const rows = csv.trim().split("\n").filter((l) => l.trim()).map((line) => {
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

interface Point { ms: number; value: number; base: number; width: number; low: number; high: number; confidence: string; drivers: string }
/** Points for the answer chart: value with its low-high range, from the time / value / low / high columns. */
export function chartPoints(table: { header: string[]; rows: string[][] }): Point[] {
  const ix = (c: string) => table.header.indexOf(c);
  const cell = (r: string[], c: string) => (ix(c) >= 0 ? (r[ix(c)] ?? "") : "");
  if (ix("time") < 0 || ix("value") < 0) return [];
  return table.rows.map((r) => {
    const value = Number(r[ix("value")]);
    const low = ix("low") >= 0 && r[ix("low")] !== "" ? Number(r[ix("low")]) : value;
    const high = ix("high") >= 0 && r[ix("high")] !== "" ? Number(r[ix("high")]) : value;
    return { ms: timeMs(r[ix("time")]), value, base: Math.min(low, high, value), width: Math.max(Math.abs(high - low), 0), low, high,
      confidence: cell(r, "confidence"), drivers: cell(r, "drivers") };
  }).filter((p) => Number.isFinite(p.ms) && Number.isFinite(p.value) && Number.isFinite(p.base) && Number.isFinite(p.width))
    .sort((a, b) => a.ms - b.ms);
}

/** The little window on hovering a point of the answer chart: the row's numbers and the model's own reasoning (its drivers) for that point. */
export function ReasonTip({ active, payload }: TooltipProps<number, string>) {
  const p = active ? (payload?.[0]?.payload as Point | undefined) : undefined;
  if (!p) return null;
  return (
    <div data-testid="harness-tip" className="max-w-72 rounded-md border border-grey-light bg-white p-2 text-xs shadow-sm">
      <div className="font-medium text-foreground">{fiTime(String(p.ms))}</div>
      <div className="tabular-nums text-muted-foreground">Forecast {p.value.toFixed(1)} €/MWh</div>
      {p.high !== p.low && <div className="tabular-nums text-muted-foreground">Likely range {p.low.toFixed(1)} – {p.high.toFixed(1)} €/MWh</div>}
      {p.confidence && <div className="text-muted-foreground">Confidence {p.confidence}</div>}
      {p.drivers && <div className="mt-1 whitespace-pre-wrap text-muted-foreground">Reasoning: {p.drivers}</div>}
    </div>
  );
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
          <Tooltip content={ReasonTip} />
          <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
          <Area dataKey="width" stackId="b" stroke="none" fill="#46bedc" fillOpacity={0.3} name="Range (low to high)" isAnimationActive={false} />
          <Line dataKey="value" stroke="#c96a00" strokeWidth={3} dot={{ r: 3 }} name="Forecast" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface Step { n: number; title: string; detail: string; think: string; state: "done" | "active" | "failed" }

/** Turns the harness progress lines into a short list of steps: one per call to the model, named by what it did. */
export function parseSteps(lines: string[], status: JobView["status"] | null): Step[] {
  const steps: Step[] = [];
  let finished = false;
  for (const line of lines) {
    const turn = line.match(/^\[turn (\d+)\/\d+\]/);
    const last = steps[steps.length - 1];
    if (turn) { steps.push({ n: Number(turn[1]), title: "Asking the model", detail: "", think: "", state: "done" }); continue; }
    if (!last) continue;
    if (line.startsWith("[think] ")) {
      try { last.think = String(JSON.parse(line.slice(8))); } catch { last.think = line.slice(8).replace(/^"|"?$/g, ""); }
      continue;
    }
    const tool = line.match(/^\[tool\] (\w+) ?(.*)$/);
    if (tool) {
      const src = tool[2].match(/"source"\s*:\s*"([^"]+)"/)?.[1];
      last.title = tool[1] === "get_data" ? `Fetching ${src ?? "data"}` : tool[1] === "run_python" ? "Running Python" : "Fetching a web page";
      continue;
    }
    const res = line.match(/^\[result\] (\d+) characters: (.*)$/);
    if (res) {
      const failed = /^['"]Error/.test(res[2]);
      last.detail = failed ? `failed: ${res[2].replace(/^['"]/, "").slice(0, 90)}` : `${Number(res[1]).toLocaleString("en-GB")} characters received`;
      continue;
    }
    if (line.startsWith("[done]")) { finished = true; if (last.title === "Asking the model") last.title = "Writing the answer"; }
  }
  if (steps.length && status === "running" && !finished) steps[steps.length - 1].state = "active";
  if (steps.length && (status === "error" || status === "stopped")) steps[steps.length - 1].state = "failed";
  return steps;
}

const Spinner = () => (
  <svg className="size-4 shrink-0 animate-spin text-orange-fill" viewBox="0 0 24 24" aria-label="in progress" role="img">
    <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
    <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

const stateText = (j: JobView | null) =>
  !j ? "Ready." : j.status === "running" ? `Running … ${Math.round(j.elapsed)} s`
    : j.status === "done" ? `Done in ${Math.round(j.elapsed)} s.` : j.status === "stopped" ? "Stopped." : "Failed. See the progress log.";

export default function HarnessPanel({ pollMs = 1000 }: { pollMs?: number }) {
  const [info, setInfo] = useState<Info | null | "offline" | "outdated">(null);
  const [model, setModel] = useState("");
  const [preset, setPreset] = useState("");
  const [job, setJob] = useState<JobView | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [keys, setKeys] = useState<Keys>({ set: [], missing: [] });
  const [keyValue, setKeyValue] = useState<Record<string, string>>({});
  const nextRef = useRef(0);
  const logRef = useRef<HTMLOListElement>(null);
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
        if (!i || !Array.isArray(i.presets) || !Array.isArray(i.models)) { setInfo("outdated"); return; }   // an older server version
        setInfo(i);
        setKeys(i.keys ?? { set: [], missing: [] });
        setModel((m) => m || i.models.find((x) => /E4B/i.test(x)) || i.models[0] || "");
        setPreset((p) => p || i.presets[0]?.id || "");
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
    fetch(`${API}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preset, model }) })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || String(r.status)); return d; })
      .then((d) => { nextRef.current = 0; setLines([]); apply(d.job); })
      .catch((e: Error) => setErr(e.message));
  };
  const saveKey = (name: string) => () => {
    setErr("");
    fetch(`${API}/keys`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, value: keyValue[name] ?? "" }) })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || String(r.status)); return d as Keys; })
      .then((k) => { setKeys(k); setKeyValue((v) => ({ ...v, [name]: "" })); })
      .catch((e: Error) => setErr(e.message));
  };
  const stop = () => { fetch(`${API}/stop`, { method: "POST" }).catch(() => setErr("Could not stop the run.")); };

  const table = job && job.answer ? parseCsvBlock(job.answer) : null;
  const cols = table ? ["time", "metric", "value", "low", "high", "confidence"].filter((c) => table.header.includes(c)) : [];
  const points = table ? chartPoints(table) : [];
  const steps = parseSteps(lines, job ? job.status : null);
  const text = job && job.answer ? splitAnswer(job.answer).text : "";

  const models = info !== null && typeof info === "object" ? info.models : [];
  return (
    <Card className="flex flex-1 flex-col gap-3 bg-white p-4">
      <h2 className="font-display text-2xl font-bold uppercase tracking-wide">Harness prediction.</h2>
      {info === null && <p className="text-muted-foreground">Looking for the harness server …</p>}
      {info === "offline" && (
        <div className="space-y-2 text-muted-foreground" data-testid="harness-offline">
          <p>The harness runs on your own computer with your local model, so it is not available on this page.</p>
          <p>To use it: open a terminal in the repo folder, run <code>./scripts/start_harness.sh</code>, then reload this page.</p>
        </div>
      )}
      {info === "outdated" && (
        <div className="space-y-2 text-muted-foreground" data-testid="harness-outdated">
          <p>The harness server that is running is an older version.</p>
          <p>Stop it (Ctrl+C in its terminal), run <code>./scripts/start_harness.sh</code> again, then reload this page.</p>
        </div>
      )}
      {info && info !== "offline" && info !== "outdated" && (
        <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">An AI model fetches live data and makes a short forecast. A live demo, not the scored entry.</p>
            <div className="flex flex-col gap-1 text-sm">
              <span className="font-medium">What to forecast</span>
              <div className="flex flex-wrap gap-2">
                {info.presets.map((p) => (
                  <Button key={p.id} size="sm" variant={preset === p.id ? "primary" : "outline"} className={preset === p.id ? solidBtn : outlineBtn} aria-pressed={preset === p.id} disabled={running} onClick={() => setPreset(p.id)}>{p.label}</Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground" data-testid="harness-about">{info.presets.find((p) => p.id === preset)?.about}</p>
            </div>
            {(keys.missing.length > 0 || keys.set.length > 0) && (
              <div className="flex flex-col gap-2 text-sm" data-testid="harness-keys">
                <span className="font-medium">API keys</span>
                <p className="text-muted-foreground">Some data sources need a key. It is saved to key.txt on this computer and not shown again.</p>
                {[...keys.missing, ...keys.set].map((n) => (
                  <div key={n} className="flex items-end gap-2">
                    <label className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="text-xs text-muted-foreground">{n}{keys.set.includes(n) ? " (saved)" : ""}</span>
                      <input aria-label={`${n} value`} type="password" autoComplete="off" className="h-9 min-w-0 rounded-md border border-input bg-white px-2 text-sm"
                        value={keyValue[n] ?? ""} onChange={(e) => setKeyValue((v) => ({ ...v, [n]: e.target.value }))} />
                    </label>
                    <Button size="sm" variant="outline" className={outlineBtn} disabled={!(keyValue[n] ?? "").trim()} onClick={saveKey(n)}>Save</Button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3">
              <Button size="sm" variant="primary" className={cn(solidBtn, "w-28")} disabled={running || !model || !preset} onClick={start}>Start run</Button>
              <Button size="sm" variant="outline" className={cn(outlineBtn, "w-20")} disabled={!running} onClick={stop}>Stop</Button>
              <span className="text-sm text-muted-foreground" data-testid="harness-state">{stateText(job)}</span>
            </div>
            {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          </div>
          <div className="flex flex-col gap-3 lg:self-start">
            <div className="flex flex-col">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="font-display text-base font-bold uppercase tracking-wide">Progress.</h3>
                <span className="text-sm text-muted-foreground" data-testid="harness-state">{stateText(job)}</span>
              </div>
              <ol ref={logRef} data-testid="harness-log" className="mt-2 rounded-lg border border-grey-light bg-white p-3 text-xs">
                {steps.length === 0 && (
                  <li className="flex items-center gap-2 text-muted-foreground">{running ? <><Spinner /> Starting the model …</> : "Nothing yet."}</li>
                )}
                {steps.map((st, i) => (
                  <li key={i} data-state={st.state} className="relative flex gap-2 pb-2.5 last:pb-0">
                    {i < steps.length - 1 && <span aria-hidden="true" className="absolute bottom-0 left-2.5 top-6 w-px bg-grey-light" />}
                    <span className="relative z-10 flex size-5 shrink-0 items-center justify-center">
                      {st.state === "active" ? <Spinner /> : (
                        <span className={cn("flex size-4 items-center justify-center rounded-full text-[0.6rem] font-bold text-white", st.state === "done" ? "bg-navy" : "bg-destructive")}>{st.state === "done" ? "✓" : "✕"}</span>
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={cn("leading-4", st.state === "failed" ? "text-destructive" : "text-foreground", st.state === "active" && "font-medium")}>Step {st.n}: {st.title}{st.state === "active" ? " …" : ""}</p>
                      {st.detail && <p className="text-[0.7rem] text-muted-foreground">{st.detail}</p>}
                      {st.think && (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs font-medium text-navy">Reasoning</summary>
                          <p data-testid="harness-think" className="mt-1 whitespace-pre-wrap rounded-md bg-bg-light p-2 text-[0.7rem] text-muted-foreground">{st.think}</p>
                        </details>
                      )}
                    </div>
                  </li>
                ))}
                {(job?.status === "error") && lines.length > 0 && <li className="pt-1 text-xs text-destructive">{lines.filter((l) => !/^\[(turn|tool|result|start|done)/.test(l)).slice(-2).join(" ")}</li>}
              </ol>
            </div>
            {job && job.answer && (
              <div className="shrink-0">
                <h3 className="font-display text-base font-bold uppercase tracking-wide">Forecast.</h3>
                {points.length > 1 && <div className="mt-2 rounded-lg border border-grey-light bg-white p-3"><AnswerChart points={points} /></div>}
                {points.length <= 1 && table && cols.length > 0 && (
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
      {settingsOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-navy/40 p-4" onClick={() => setSettingsOpen(false)}>
          <div role="dialog" aria-label="Settings" data-testid="harness-keys" className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-border bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display text-2xl font-bold uppercase tracking-wide">Settings.</h3>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium">Model</span>
              <select aria-label="harness model" className="h-9 w-full rounded-md border border-input bg-white px-3 text-sm" value={model} disabled={running} onChange={(e) => setModel(e.target.value)}>
                {models.length === 0 && <option value="">No model found: start the Llama app</option>}
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
            <b className="text-sm font-medium">API keys</b>
            {keys.set.length > 0 && (
              <ul className="flex flex-col gap-1 text-sm">
                {keys.set.map((n) => <li key={n} className="flex items-center justify-between rounded-md bg-bg-light px-3 py-2"><span>{n}</span><span className="text-muted-foreground">✓ set</span></li>)}
              </ul>
            )}
            {keys.missing.length > 0 ? (
              <div className="flex flex-col gap-3 text-sm">
                <label className="flex flex-col gap-1">
                  <span className="font-medium">Key</span>
                  <select aria-label="key name" className="h-9 w-full rounded-md border border-input bg-white px-3 text-sm" value={keyName} onChange={(e) => setKeyName(e.target.value)}>
                    {keys.missing.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-medium">Value</span>
                  <input aria-label="key value" type="password" autoComplete="off" className="h-9 w-full rounded-md border border-input bg-white px-3 text-sm" value={keyValue} onChange={(e) => setKeyValue(e.target.value)} />
                </label>
              </div>
            ) : <p className="text-sm">All keys are set.</p>}
            <div className="grid grid-cols-2 gap-2">
              <Button size="sm" variant="outline" className={cn(outlineBtn, "w-full")} onClick={() => setSettingsOpen(false)}>Close</Button>
              <Button size="sm" variant="primary" className={cn(solidBtn, "w-full")} disabled={!keyValue.trim() || keys.missing.length === 0} onClick={saveKey}>Save</Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
