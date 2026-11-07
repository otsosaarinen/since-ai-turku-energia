import { useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, cn } from "@/design-system/the-reading-room-3066fa";

// Panel for the "Harness prediction" box: starts a run of harness/harness.py on THIS computer (through the local control server,
// scripts/start_harness.sh, reached via the Vite proxy /harness-api), shows its progress and the answer. On a hosted copy of the website
// (e.g. Vercel) the server does not exist, so the panel only explains how to start it.

const API = "/harness-api";
interface Preset { id: string; label: string; about: string }
interface Info { llama_url: string; models: string[]; presets: Preset[] }
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
  const [info, setInfo] = useState<Info | null | "offline" | "outdated">(null);
  const [model, setModel] = useState("");
  const [preset, setPreset] = useState("");
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
        if (!i || !Array.isArray(i.presets) || !Array.isArray(i.models)) { setInfo("outdated"); return; }   // an older server version
        setInfo(i);
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
  const stop = () => { fetch(`${API}/stop`, { method: "POST" }).catch(() => setErr("Could not stop the run.")); };

  const table = job && job.answer ? parseCsvBlock(job.answer) : null;
  const cols = table ? ["time", "metric", "value", "low", "high", "confidence"].filter((c) => table.header.includes(c)) : [];
  const points = table ? chartPoints(table) : [];
  const text = job && job.answer ? splitAnswer(job.answer).text : "";

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
      {info === "outdated" && (
        <div className="space-y-2 text-muted-foreground" data-testid="harness-outdated">
          <p>The harness server that is running is an older version.</p>
          <p>Stop it (Ctrl+C in its terminal), run <code>./scripts/start_harness.sh</code> again, then reload this page.</p>
        </div>
      )}
      {info && info !== "offline" && info !== "outdated" && (
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
            <div className="flex flex-col gap-1 text-sm">
              <span className="font-medium">What to forecast</span>
              <div className="flex flex-wrap gap-2">
                {info.presets.map((p) => (
                  <Button key={p.id} size="sm" variant={preset === p.id ? "primary" : "outline"} className={preset === p.id ? solidBtn : outlineBtn} aria-pressed={preset === p.id} disabled={running} onClick={() => setPreset(p.id)}>{p.label}</Button>
                ))}
              </div>
              <p className="mt-1 text-muted-foreground" data-testid="harness-about">{info.presets.find((p) => p.id === preset)?.about}</p>
            </div>
            <div className="flex items-center gap-3">
              <Button size="sm" variant="primary" className={cn(solidBtn, "w-28")} disabled={running || !model || !preset} onClick={start}>Start run</Button>
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
