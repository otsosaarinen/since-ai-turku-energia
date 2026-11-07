import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { Alert, AlertTitle, Button, Card, Hills, cn } from "@/design-system/the-reading-room-3066fa";
import type { Cell, ChartPoint, MethodKey, NumKey, Payload, Row, SetKey, ToggleId, VariantIndex } from "./types";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// ---------------------------------------------------------------------------------------------------------------------
// Look and feel follows the Turku Energia graphic guidelines (Graafinen ohjeisto 2024), web section:
// white base, orange only as an accent, blue/grey for structure (AA contrast), bold condensed capital headlines that end in a
// full stop, plain and warm wording. The logo is NOT recreated here (the guide forbids building it from an orange bar and text).
// ---------------------------------------------------------------------------------------------------------------------

// The two ways of predicting. "harness" has no forecasts yet: when its two files (same format as validation.json / final.json)
// appear in web/public/data/, the box switches the chart to them automatically.
const METHODS: Record<MethodKey, { title: string; sub: string; files: Record<SetKey, string> }> = {
  current: { title: "Machine-learning model", sub: "LightGBM, trained on 1 June – 4 October.", files: { validation: "validation", final: "final" } },
  harness: { title: "Harness prediction", sub: "A second method. Not connected yet.", files: { validation: "harness_validation", final: "harness_final" } },
};
// Input toggles of the current model. Each combination is a separately trained model variant computed by scripts/run_variants.py;
// the key has one digit per toggle (1 = on, 0 = off), "111" is the normal model served by validation.json / final.json.
const TOGGLES: { id: ToggleId; label: string }[] = [
  { id: "solar", label: "Solar forecast" },
  { id: "wind", label: "Wind forecast" },
  { id: "consumption", label: "Consumption forecast" },
];
const SETS: Record<SetKey, { label: string }> = {
  validation: { label: "Validation 7 Sep – 4 Oct" },
  final: { label: "Test forecast 5 Oct – 1 Nov" },
};
const HELP: Record<string, string> = {
  spot_price: "the day-ahead price of electricity", consumption_forecast_da: "the forecast of electricity consumption",
  wind_forecast_da: "the wind power forecast", solar_forecast_da: "the solar power forecast",
  residual_load_forecast: "the electricity demand left after wind and solar", latest_imbalance_price: "the latest imbalance prices",
  imbalance_minus_spot_history: "how far recent imbalance prices were from the day-ahead price", mfrr_direction_history: "whether the grid recently needed more or less power",
  mfrr_prices_and_activation: "prices and use of the manual balancing reserve", afrr_activity: "use of the automatic balancing reserve", cross_border_flows: "electricity flows to and from neighbouring countries",
  neighbour_imbalance_prices: "imbalance prices in Sweden and Estonia", same_time_previous_days_imbalance: "the imbalance price at the same time on previous days",
  consumption_actual: "measured electricity consumption", production_actual: "measured electricity production", neighbour_load_forecasts: "consumption forecasts of neighbouring countries",
  fi_ee_capacity: "the transmission capacity between Finland and Estonia", calendar: "the time of day and the weekday", forecast_horizon: "how far ahead the hour is",
};
// Data is stored in UTC; everything shown on the page is Finnish time (Europe/Helsinki, incl. the 25 Oct clock change).
const FI = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Helsinki", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const fiParts = (t: number | string): Record<string, string> => Object.fromEntries(FI.formatToParts(new Date(t)).map((p) => [p.type, p.value]));
const hhmm = (t: number | string) => { const p = fiParts(t); return `${p.hour}:${p.minute}`; };
const mdOf = (t: number | string) => { const p = fiParts(t); return `${p.day}/${p.month}/${p.year}`; };   // dd/mm/yyyy
const isoDayToFi = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}`;
const dayOf = (t: number | string) => { const p = fiParts(t); return `${p.year}-${p.month}-${p.day}`; };
const eur = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(1)} €/MWh`);

// chart colours: deepened brand orange for the forecast (the plain orange is too light to read on white), red for the real prices
// (easy to tell apart from the forecast), blue for the range, grey for the earlier forecast
const C = { grid: "var(--border)", axis: "var(--muted-foreground)", p50: "#c96a00", band: "#46bedc", actual: "var(--destructive)", earlier: "#7d7d7d", now: "var(--foreground)" };
const selectCls = "h-9 rounded-md border border-input bg-white px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30";
const solidBtn = "border-2 border-orange-fill bg-orange-fill text-white hover:bg-orange-fill/90";
const outlineBtn = "border-2 border-navy bg-white text-navy hover:bg-bg-light";
const h2 = "font-display font-bold uppercase tracking-wide";
const EMPTY = new Map<number, Row>();

/** Small "i" button that explains something on hover, focus or tap. */
function Info({ text, align = "center" }: { text: string; align?: "left" | "right" | "center" }) {
  const id = useId();
  const pos = align === "left" ? "left-0" : align === "right" ? "right-0" : "left-1/2 -translate-x-1/2";
  return (
    <span className="group relative ml-1 inline-flex align-middle">
      <button type="button" aria-describedby={id} aria-label="More information"
        className="grid size-4 place-items-center rounded-full border border-muted-foreground text-[10px] font-bold leading-none text-muted-foreground hover:bg-bg-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">i</button>
      <span id={id} role="tooltip"
        className={cn("pointer-events-none invisible absolute top-full z-30 mt-2 w-64 rounded-md bg-navy p-3 text-left font-sans text-xs font-normal normal-case leading-snug tracking-normal text-white opacity-0 shadow-lg transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100", pos)}>
        {text}
      </span>
    </span>
  );
}

/** What you see when you point at the chart. */
function ChartTip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  if (!active || !payload || !payload.length) return null;
  const r = payload[0].payload;
  const real = r.realKnown ?? r.realLater;
  return (
    <div className="rounded-md border border-border bg-white p-3 text-sm shadow-lg">
      <p className={cn(h2, "text-base")}>{mdOf(r.ms)} {hhmm(r.ms)}</p>
      {r.p50 != null && <>
        <p>Forecast (most likely price): <b>{eur(r.p50)}</b></p>
        <p>Likely range: {eur(r.p10)} to {eur(r.p90)}</p>
      </>}
      {real != null && <p>Real price: <b>{eur(real)}</b></p>}
      {r.prevP50 != null && <p className="text-muted-foreground">Forecast made 3 h earlier: {eur(r.prevP50)}</p>}
    </div>
  );
}

function Chip({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex h-[4.25rem] w-28 shrink-0 flex-col items-center justify-center rounded-md bg-bg-light px-2 text-center">
      <div className="font-serif text-2xl font-light leading-none tabular-nums text-navy">{value}</div>
      <div className="mt-1 text-xs leading-tight text-muted-foreground">{label}</div>
    </div>
  );
}

function useData(name: string) {
  const [d, setD] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;                       // ignore an answer that arrives after the choice changed again
    setLoading(true); setErr(null);              // the previous data stays on screen meanwhile (no blink)
    fetch(`/data/${name}.json`)
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((x) => { if (!cancelled) { setD(x); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setErr(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [name]);
  return { d, err, loading };
}

function index(d: Payload) {
  const ci: Record<string, number> = Object.fromEntries(d.cols.map((c, i) => [c, i]));
  const by = new Map<string, Cell[][]>();
  for (const r of d.rows) { const o = r[ci.forecast_origin_utc] as string; if (!by.has(o)) by.set(o, []); by.get(o)!.push(r); }
  const rowObj = (r: Cell[]) => Object.fromEntries(d.cols.map((c, i) => [c, r[i]])) as unknown as Row;
  return { origins: [...by.keys()].sort(), get: (o: string): Row[] => (by.get(o) || []).map(rowObj) };
}

export default function App() {
  const [set, setSet] = useState<SetKey>("validation");
  const [method, setMethod] = useState<MethodKey>("current");
  const [on, setOn] = useState<Record<ToggleId, boolean>>({ solar: true, wind: true, consumption: true });
  const key = TOGGLES.map((t) => (on[t.id] ? "1" : "0")).join("");
  const variant = method === "current" && key !== "111";
  const [vIndex, setVIndex] = useState<VariantIndex | null>(null);
  useEffect(() => { fetch("/data/variants/index.json").then((r) => (r.ok ? r.json() : null)).then(setVIndex).catch(() => setVIndex(null)); }, []);
  const { d, err, loading } = useData(variant ? `variants/${set}_${key}` : METHODS[method].files[set]);
  const ix = useMemo(() => (d ? index(d) : null), [d]);
  // Position in the list of forecast hours. The integer part is a forecast hour, the fraction is the time in between: the chart slides
  // and blends the two neighbouring forecasts, so stepping and playing look smooth even though forecasts exist only once an hour.
  const TICK = 33;                                   // ms between animation frames (about 30 per second)
  const [fpos, setFpos] = useState(0);
  const fposRef = useRef(0), targetRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const playingRef = useRef(false);
  const [speed, setSpeed] = useState(1);              // forecast hours per second while playing
  const speedRef = useRef(1);
  speedRef.current = speed;
  const [animating, setAnimating] = useState(false);  // gliding towards targetRef after a button click
  const last = ix ? ix.origins.length - 1 : 0;
  const clamp = (v: number) => Math.max(0, Math.min(last, v));
  const apply = (v: number) => { fposRef.current = v; setFpos(v); };
  const goTo = (i: number, glide: boolean) => {
    const t = clamp(i);
    playingRef.current = false; setPlaying(false);
    targetRef.current = t;
    if (glide) setAnimating(true); else apply(t);
  };
  const step = (k: number) => goTo(Math.round(targetRef.current) + k, true);
  const togglePlay = () => {
    if (playingRef.current) { goTo(Math.round(fposRef.current), true); return; }
    if (fposRef.current >= last - 0.001) apply(0);
    playingRef.current = true; setPlaying(true);
  };
  const pos = ix ? Math.max(0, Math.min(last, Math.round(fpos))) : 0;
  const lastOriginRef = useRef<string | null>(null);
  // a new forecast file: keep the hour if it exists there (switches, method), otherwise start from the beginning
  useEffect(() => {
    if (!ix) return;
    if (!lastOriginRef.current || ix.origins.indexOf(lastOriginRef.current) < 0) { goTo(0, false); }
  }, [ix]);                                             // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (ix) lastOriginRef.current = ix.origins[pos]; });
  // the animation clock only runs while playing or gliding
  useEffect(() => {
    if (!ix || !(playing || animating)) return undefined;
    const id = setInterval(() => {
      let f = fposRef.current;
      if (playingRef.current) {
        f += (speedRef.current * TICK) / 1000;
        if (f >= last) { f = last; playingRef.current = false; setPlaying(false); }
        targetRef.current = f; apply(f);
      } else {
        const diff = targetRef.current - f;
        if (Math.abs(diff) < 0.004) { apply(targetRef.current); setAnimating(false); } else apply(f + diff * 0.28);
      }
    }, TICK);
    return () => clearInterval(id);
  }, [ix, last, playing, animating]);                   // eslint-disable-line react-hooks/exhaustive-deps
  const rowCache = useMemo(() => new Map(), [ix]);
  // Fixed price axis for the whole period, so the numbers on the left never move while time moves or plays: from the 1st percentile of the
  // low end to the 99.9th percentile of the forecast line, the 99th percentile of the high end of the likely range and the 97th for real prices, rounded outwards to steps of 50 EUR/MWh.
  // Rare larger values run off the chart (the tooltip still shows them).
  const yAxis = useMemo(() => {
    if (!d) return null;
    const col = (c: string): number[] => { const i = d.cols.indexOf(c); return i < 0 ? [] : (d.rows.map((r) => r[i]).filter((v) => v != null) as number[]).sort((a, b) => a - b); };
    const pick = (a: number[], p: number) => (a.length ? a[Math.min(a.length - 1, Math.floor(p * (a.length - 1)))] : null);
    const real = col("actual_imbalance_price");
    const lows = [pick(col("p10"), 0.01), pick(real, 0.01)].filter((v): v is number => v != null);
    const highs = [pick(col("p50"), 0.999), pick(col("p90"), 0.99), pick(real, 0.97)].filter((v): v is number => v != null);
    const step = 50;
    const lo = Math.min(0, Math.floor(Math.min(...lows) / step) * step), hi = Math.max(step, Math.ceil(Math.max(...highs) / step) * step);
    const ticks: number[] = [];
    for (let t = lo; t <= hi; t += step) ticks.push(t);
    return { lo, hi, ticks };
  }, [d]);
  const actualAt = useMemo(() => {
    const m = new Map<string, number>();
    if (!d || !d.hasActuals) return m;
    const ti = d.cols.indexOf("delivery_start_utc"), ai = d.cols.indexOf("actual_imbalance_price");
    for (const r of d.rows) if (r[ai] != null) m.set(r[ti] as string, r[ai] as number);
    return m;
  }, [d]);

  // render helpers (plain functions, not inner components: inner components would remount the controls on every render)
  const shell = (children: React.ReactNode) => (
    <main className="relative min-h-screen overflow-hidden bg-background font-sans text-foreground lg:h-screen">
      {/* the brand wave as a calm light-blue background */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <Hills tone="sky" className="opacity-60" />
        <Hills tone="primary" className="h-1/5 opacity-90" />
      </div>
      <div className={cn("relative z-10 mx-auto flex min-h-screen w-full max-w-[1500px] flex-col gap-3 p-4 transition-opacity lg:h-screen", loading && "opacity-70")}>{children}</div>
    </main>
  );
  const header = (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-4xl font-bold uppercase leading-none tracking-wide">Imbalance price forecast<span className="text-brand">.</span></h1>
          <p className="mt-1 text-sm text-muted-foreground">Since AI Hackathon 2026, Turku Energia challenge. The next 10 hours.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Period
            <Info align="right" text="Validation: a practice month with known real prices. Test forecast: the month that will be scored; its prices are unknown." />
          </span>
          {(Object.entries(SETS) as [SetKey, { label: string }][]).map(([k, v]) => (
            <Button key={k} size="sm" variant={set === k ? "primary" : "outline"} className={set === k ? solidBtn : outlineBtn} onClick={() => setSet(k)}>{v.label}</Button>
          ))}
        </div>
      </header>
      {/* the two ways to predict: the highlighted box decides what the chart shows */}
      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.entries(METHODS) as [MethodKey, (typeof METHODS)[MethodKey]][]).map(([k, m]) => {
          const active = method === k;
          return (
            <button key={k} type="button" aria-pressed={active} onClick={() => setMethod(k)}
              className={cn("flex flex-col items-start rounded-lg border-2 border-b-4 px-5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active ? "border-orange-fill border-b-brand bg-orange-fill text-white shadow-md" : "border-grey-light bg-white/90 text-foreground hover:bg-bg-light")}>
              <span className="font-display text-xl font-bold uppercase tracking-wide">{m.title}</span>
              <span className={cn("text-sm", active ? "text-white/90" : "text-muted-foreground")}>{m.sub}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
  const message = (title: string, children: React.ReactNode) => (
    <Card className="flex flex-1 items-center justify-center bg-white/90 p-8 text-center">
      <div className="max-w-xl space-y-3">
        <p className={cn(h2, "text-3xl")}>{title}.</p>
        <div className="text-muted-foreground">{children}</div>
      </div>
    </Card>
  );
  const notConnected = message(`${METHODS[method].title} is not connected yet`, <p>
    Its forecasts have not been added to the repo. When they are, put them in <code>web/public/data/{METHODS[method].files[set]}.json</code>
    {" "}(same format as <code>{METHODS.current.files[set]}.json</code>) and reload this page. The chart then appears here automatically.</p>);
  const notComputed = message("This combination has not been computed yet", <div className="space-y-3">
    <p>Run <code>uv run scripts/run_variants.py</code> to create the forecasts for every on/off combination of the inputs, then reload.</p>
    <Button size="sm" variant="outline" className={outlineBtn} onClick={() => setOn({ solar: true, wind: true, consumption: true })}>Switch all inputs on</Button></div>);
  if (err && method !== "current") return shell(<>{header}{notConnected}</>);
  if (err && variant) return shell(<>{header}{notComputed}</>);
  if (err) return shell(<>{header}
    <Alert variant="destructive"><div><AlertTitle>Could not load the forecast</AlertTitle>/data/{set}.json ({err}). Run <code>uv run scripts/export_web_data.py</code> first.</div></Alert></>);
  if (!ix) return shell(<>{header}<p>Loading…</p></>);

  const origin = ix.origins[pos];
  const rows = ix.get(origin);
  const hasAct = d!.hasActuals;
  const days = [...new Set(ix.origins.map(dayOf))];

  const Q = 15 * 60 * 1000, HOUR = 4 * Q;
  const o0 = Date.parse(origin);
  const iso = (ms: number) => new Date(ms).toISOString().slice(0, 19) + "Z";
  // Forecast rows of origin k by delivery time (cached).
  const forecastAt = (k: number): Map<number, Row> => {
    if (k < 0 || k > last) return EMPTY;
    let m = rowCache.get(k);
    if (!m) { m = new Map(ix.get(ix.origins[k]).map((r) => [Date.parse(r.delivery_start_utc), r])); rowCache.set(k, m); }
    return m;
  };
  // Smooth chart: T is the (possibly in-between) time the forecast was made. The two neighbouring forecasts k0 and k1 are blended
  // with weight sf, and so are the forecasts made 3 h earlier. The time axis slides with T.
  const f = clamp(fpos), k0 = Math.floor(f), k1 = Math.min(k0 + 1, last), sf = f - k0;
  const oMs = (k: number) => Date.parse(ix.origins[k]);
  const T = oMs(k0) + sf * (oMs(k1) - oMs(k0));
  const A = forecastAt(k0), B = forecastAt(k1), EA = forecastAt(k0 - 3), EB = forecastAt(k1 - 3);
  const blend = (ma: Map<number, Row>, mb: Map<number, Row>, ms: number, key2: NumKey): number | null => {
    const a2 = ma.get(ms), b2 = mb.get(ms);
    if (a2 && b2) return a2[key2] + (b2[key2] - a2[key2]) * sf;
    const r = b2 || a2;
    return r ? r[key2] : null;
  };
  const knownUntil = T - 75 * 60 * 1000;               // real prices are published about 75 min after the quarter-hour starts
  const lastKnown = Math.floor(knownUntil / Q) * Q;
  const chart: ChartPoint[] = [];
  for (let ms = Math.ceil((T - 3 * HOUR - Q) / Q) * Q; ms <= T + 10 * HOUR; ms += Q) {
    const fut = ms >= T, past = ms < T;
    const p10 = fut ? blend(A, B, ms, "p10") : null, p90 = fut ? blend(A, B, ms, "p90") : null;
    const e10 = past ? blend(EA, EB, ms, "p10") : null, e90 = past ? blend(EA, EB, ms, "p90") : null;
    const real = actualAt.get(iso(ms)) ?? null;
    chart.push({
      ms,
      base: p10, width: p10 == null || p90 == null ? null : p90 - p10, p10, p50: fut ? blend(A, B, ms, "p50") : null, p90,
      prevBase: e10, prevWidth: e10 == null || e90 == null ? null : e90 - e10, prevP50: past ? blend(EA, EB, ms, "p50") : null,
      realKnown: ms <= knownUntil ? real : null, realLater: ms >= lastKnown ? real : null,
    });
  }
  const ticks: number[] = [];
  for (let t = Math.ceil((T - 3 * HOUR) / HOUR) * HOUR; t <= T + 9.75 * HOUR; t += HOUR) ticks.push(t);
  const withAct = rows.filter((r) => hasAct && r.actual_imbalance_price != null) as (Row & { actual_imbalance_price: number })[];
  const mae = withAct.length ? withAct.reduce((s, r) => s + Math.abs(r.p50 - r.actual_imbalance_price), 0) / withAct.length : null;
  const cov = withAct.length ? withAct.filter((r) => r.actual_imbalance_price >= r.p10 && r.actual_imbalance_price <= r.p90).length / withAct.length : null;
  const maxHi = Math.max(...rows.map((r) => r.p_spike_high)); const maxLo = Math.max(...rows.map((r) => r.p_spike_low));
  const upShare = rows.reduce((s, r) => s + r.p_up, 0) / rows.length;
  const hiRow = rows.reduce((a, r) => (r.p_spike_high > a.p_spike_high ? r : a), rows[0]);
  const drivers = (rows[0].top_drivers || "").split(";").filter(Boolean);

  const dirText = upShare > 0.55 ? "The grid probably needs more power: prices lean above the day-ahead price."
    : upShare < 0.45 ? "The grid probably needs less power: prices lean below the day-ahead price."
      : "It is unclear whether the grid needs more or less power.";
  const lo50 = Math.round(Math.min(...rows.map((r) => r.p50))), hi50 = Math.round(Math.max(...rows.map((r) => r.p50)));
  const spikeText = maxHi >= 0.3 ? `High price spike possible around ${hhmm(hiRow.delivery_start_utc)} (${(maxHi * 100).toFixed(0)} %).` : "No unusual price spikes expected.";
  const priceText = `Most likely price ${lo50} to ${hi50} €/MWh. ${spikeText}`;
  const driversText = `Main drivers: ${drivers.map((x, i) => `${i + 1}. ${HELP[x] || x.replaceAll("_", " ")}`).join("; ")}.`;
  const pct = (v: number) => `${(v * 100).toFixed(0)} %`;

  return shell(
    <>
      {header}
      {/* one slim strip: what it means, the main drivers, the key numbers */}
      <Card className="flex flex-wrap items-center gap-x-6 gap-y-3 border-l-4 border-l-brand bg-white/95 p-3 lg:h-32 lg:flex-nowrap lg:overflow-visible">
        <div className="min-w-64 flex-1 lg:min-w-0">
          <h2 className={cn(h2, "text-base")}>Summary.</h2>
          <p className="line-clamp-1 leading-snug" title={dirText}>{dirText}</p>
          <p className="mt-1 line-clamp-1 leading-snug" title={priceText}>{priceText}</p>
          <p className="mt-1 line-clamp-2 text-sm leading-snug text-muted-foreground" title={driversText}>{driversText}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Chip value={pct(maxHi)} label="high price spike" />
          <Chip value={pct(maxLo)} label="low price spike" />
          <Chip value={pct(upShare)} label="grid needs more power" />
          {hasAct && <Chip value={mae == null ? "–" : mae.toFixed(1)} label="average error, €/MWh" />}
          {hasAct && <Chip value={cov == null ? "–" : pct(cov)} label="real price in range" />}
          <Info align="right" text="Spike: chance the price ends up over 50 €/MWh above (high) or below (low) the day-ahead price. Error and range need real prices." />
        </div>
      </Card>

      {/* the chart in the middle, as big as possible */}
      <Card className="flex min-h-[26rem] flex-1 flex-col bg-white/95 p-4">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h2 className={cn(h2, "text-2xl")}>Price forecast.
          </h2>
          <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2">
            <Button size="sm" variant="outline" className={outlineBtn} onClick={() => step(-24)}>◀ 1 day</Button>
            <Button size="sm" variant="outline" className={outlineBtn} onClick={() => step(-1)}>◀ 1 h</Button>
            <select aria-label="date" className={selectCls} value={dayOf(origin)} onChange={(e) => { const i = ix.origins.findIndex((x) => dayOf(x) === e.target.value); if (i >= 0) goTo(i, false); }}>
              {days.map((dd) => <option key={dd} value={dd}>{isoDayToFi(dd)}</option>)}
            </select>
            <input type="range" aria-label="whole period" className="min-w-32 max-w-md flex-1 accent-brand" min={0} max={last} step="any" value={fpos} onChange={(e) => goTo(+e.target.value, false)} />
            <b data-testid="when" className="font-display text-xl tabular-nums text-navy">{mdOf(origin)} {hhmm(origin)}</b>
            <Button size="sm" variant="outline" className={outlineBtn} onClick={() => step(1)}>1 h ▶</Button>
            <Button size="sm" variant="outline" className={outlineBtn} onClick={() => step(24)}>1 day ▶</Button>
            <Button size="sm" variant="primary" className={cn(solidBtn, "w-24")} onClick={togglePlay}>{playing ? "❚❚ Pause" : "▶ Play"}</Button>
            <Button size="sm" variant="outline" className={cn(outlineBtn, "w-14")} aria-label={`Playback speed ${speed} hours per second`}
              onClick={() => setSpeed(speed === 1 ? 3 : speed === 3 ? 10 : 1)}>{speed}×</Button>
          </div>
        </div>
        <div className="mt-2 flex min-h-72 flex-1 gap-4">
        {method === "current" && (
          <aside className="flex w-56 shrink-0 flex-col gap-3 border-r border-grey-light pr-4" data-testid="toggles">
            <div className="text-sm text-muted-foreground">
              <b className="font-medium text-foreground">Forecast inputs.</b> Switch one off to see a model trained without it.
            </div>
            {TOGGLES.map((t) => (
              <label key={t.id} className="flex cursor-pointer items-center gap-2 text-sm">
                <button type="button" role="switch" aria-checked={on[t.id]} aria-label={t.label} onClick={() => setOn({ ...on, [t.id]: !on[t.id] })}
                  className={cn("relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", on[t.id] ? "bg-orange-fill" : "bg-grey-brand")}>
                  <span className={cn("absolute top-0.5 size-5 rounded-full bg-white shadow transition-all", on[t.id] ? "left-[1.375rem]" : "left-0.5")} />
                </button>
                <span><b className="font-medium">{t.label}</b> <span className="text-muted-foreground">{on[t.id] ? "on" : "off"}</span></span>
              </label>
            ))}
            <div className="min-h-16 text-sm text-muted-foreground" data-testid="variant-metrics">
              {vIndex && vIndex.metrics && vIndex.metrics[key] && vIndex.metrics["111"] && (<>
                Average error on the validation month: <b className="text-foreground">{vIndex.metrics[key].mae.toFixed(1)}</b> €/MWh
                {key !== "111" && <> ({(vIndex.metrics[key].mae - vIndex.metrics["111"].mae >= 0 ? "+" : "") + (vIndex.metrics[key].mae - vIndex.metrics["111"].mae).toFixed(2)} vs all inputs on)</>}
              </>)}
            </div>
          </aside>
        )}
        <div className="min-w-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chart} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis type="number" dataKey="ms" domain={[T - 3 * HOUR, T + 9.75 * HOUR]} allowDataOverflow ticks={ticks} tickFormatter={hhmm} stroke={C.axis} fontSize={12} />
              <YAxis domain={yAxis ? [yAxis.lo, yAxis.hi] : ["auto", "auto"]} ticks={yAxis ? yAxis.ticks : undefined} allowDataOverflow stroke={C.axis} fontSize={12} unit=" €" width={56} />
              <Tooltip content={<ChartTip />} />
              <Area dataKey="prevBase" stackId="c" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
              <Area dataKey="prevWidth" stackId="c" stroke="none" fill={C.earlier} fillOpacity={0.15} name="Range of the earlier forecast" isAnimationActive={false} />
              <Line dataKey="prevP50" stroke={C.earlier} strokeWidth={2} strokeDasharray="2 3" dot={false} name="Forecast made 3 h earlier" isAnimationActive={false} />
              <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
              <Area dataKey="width" stackId="b" stroke="none" fill={C.band} fillOpacity={0.28} name="Likely range (8 times out of 10)" isAnimationActive={false} />
              <Line dataKey="p50" stroke={C.p50} strokeWidth={3} dot={false} name="Forecast (most likely price)" isAnimationActive={false} />
              {hasAct && <Line dataKey="realKnown" stroke={C.actual} strokeWidth={2} dot={false} name="Real price (already published)" isAnimationActive={false} />}
              {hasAct && <Line dataKey="realLater" stroke={C.actual} strokeDasharray="5 3" strokeWidth={2} dot={false} name="Real price (published later)" isAnimationActive={false} />}
              <ReferenceLine x={T} stroke={C.now} strokeWidth={2} label={{ value: "Forecast made", position: "insideTopLeft", fill: "var(--foreground)", fontSize: 12 }} />
              <ReferenceLine y={0} stroke={C.axis} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Real prices arrive about 1 hour late, so the forecast starts blind: at {hhmm(origin)} the latest known price is from {hhmm(iso(o0 - 75 * 60 * 1000))}. Finnish time.
        </p>
      </Card>
    </>
  );
}
