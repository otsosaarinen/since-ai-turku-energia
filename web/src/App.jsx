import React, { useEffect, useMemo, useState } from "react";
import {
  Alert, AlertTitle, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Hills, Stat,
} from "@/design-system/the-reading-room-3066fa";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const SETS = { validation: "Validation 7 Sep – 4 Oct (with actuals)", final: "Test forecast 5 Oct – 1 Nov" };
const HELP = {
  spot_price: "the day-ahead spot price", consumption_forecast_da: "the day-ahead consumption forecast",
  wind_forecast_da: "the wind power forecast", solar_forecast_da: "the solar power forecast",
  residual_load_forecast: "residual load (consumption minus wind and solar)", latest_imbalance_price: "the latest imbalance prices",
  imbalance_minus_spot_history: "recent imbalance prices relative to spot", mfrr_direction_history: "the recent regulation direction",
  mfrr_prices_and_activation: "mFRR prices and activations", afrr_activity: "aFRR activity", cross_border_flows: "cross-border flows",
  neighbour_imbalance_prices: "neighbouring-area imbalance prices", same_time_previous_days_imbalance: "the imbalance price at the same time on previous days",
  consumption_actual: "measured consumption", production_actual: "measured production", neighbour_load_forecasts: "neighbouring-area load forecasts",
  fi_ee_capacity: "the Finland–Estonia transfer capacity", calendar: "time of day and weekday", forecast_horizon: "how far ahead",
};
// Data is stored in UTC; everything shown on the page is Finnish time (Europe/Helsinki, incl. the 25 Oct clock change).
const FI = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Helsinki", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const fiParts = (t) => Object.fromEntries(FI.formatToParts(new Date(t)).map((p) => [p.type, p.value]));
const hhmm = (t) => { const p = fiParts(t); return `${p.hour}:${p.minute}`; };
const mdOf = (t) => { const p = fiParts(t); return `${p.day}/${p.month}/${p.year}`; };   // dd/mm/yyyy
const isoDayToFi = (d) => `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}`;
const dayOf = (t) => { const p = fiParts(t); return `${p.year}-${p.month}-${p.day}`; };

// chart colours come from the design system tokens
const C = {
  grid: "var(--border)", axis: "var(--muted-foreground)", p50: "var(--primary-strong)", band: "var(--chart-2)",
  actual: "var(--destructive)", earlier: "var(--muted-foreground)", now: "var(--foreground)",
};
const tip = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "var(--radius)", color: "var(--popover-foreground)" };
const selectCls = "h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30";

function useData(name) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setD(null); setErr(null);
    fetch(`/data/${name}.json`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(setD).catch((e) => setErr(String(e)));
  }, [name]);
  return { d, err };
}

function index(d) {
  const ci = Object.fromEntries(d.cols.map((c, i) => [c, i]));
  const by = new Map();
  for (const r of d.rows) { const o = r[ci.forecast_origin_utc]; if (!by.has(o)) by.set(o, []); by.get(o).push(r); }
  const rowObj = (r) => Object.fromEntries(d.cols.map((c, i) => [c, r[i]]));
  return { origins: [...by.keys()].sort(), get: (o) => (by.get(o) || []).map(rowObj) };
}

export default function App() {
  const [set, setSet] = useState("validation");
  const { d, err } = useData(set);
  const ix = useMemo(() => (d ? index(d) : null), [d]);
  const [origin, setOrigin] = useState(null);
  useEffect(() => { if (ix) setOrigin(ix.origins[0]); }, [ix]);
  const actualAt = useMemo(() => {
    const m = new Map();
    if (!d || !d.hasActuals) return m;
    const ti = d.cols.indexOf("delivery_start_utc"), ai = d.cols.indexOf("actual_imbalance_price");
    for (const r of d.rows) if (r[ai] != null) m.set(r[ti], r[ai]);
    return m;
  }, [d]);

  const shell = (children) => (
    <main className="relative min-h-screen overflow-hidden bg-background font-sans text-foreground lg:h-screen">
      {/* the brand wave is the page background */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <Hills tone="sky" className="opacity-80" />
        <Hills tone="primary" className="h-1/5 opacity-90" />
      </div>
      <div className="relative z-10 flex min-h-screen flex-col gap-3 p-4 lg:h-screen">{children}</div>
    </main>
  );
  const header = (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <Badge variant="primary">Turku Energia</Badge>
        <h1 className="font-serif text-3xl font-light leading-none">Imbalance price forecast <span className="text-muted-foreground">· next 10 h</span></h1>
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(SETS).map(([k, v]) => (
          <Button key={k} size="sm" variant={set === k ? "primary" : "outline"} className={set === k ? "" : "bg-card/80"} onClick={() => setSet(k)}>{v}</Button>
        ))}
      </div>
    </header>
  );

  if (err) return (
    shell(<><div>{header}</div>
      <Alert variant="destructive"><div><AlertTitle>Could not load the forecast</AlertTitle>/data/{set}.json ({err}). Run <code>uv run scripts/export_web_data.py</code> first.</div></Alert></>)
  );
  if (!ix || !origin || !ix.origins.includes(origin)) return shell(<><div>{header}</div><p>Loading…</p></>);

  const rows = ix.get(origin);
  const hasAct = d.hasActuals;
  const days = [...new Set(ix.origins.map(dayOf))];
  const pos = ix.origins.indexOf(origin);
  const step = (k) => setOrigin(ix.origins[Math.min(ix.origins.length - 1, Math.max(0, pos + k))]);

  const Q = 15 * 60 * 1000, o0 = Date.parse(origin);
  const iso = (ms) => new Date(ms).toISOString().slice(0, 19) + "Z";
  // past: (a) real prices already published at the origin (published ~60 min after the quarter-hour ends),
  // (b) real prices of the unpublished last hour, drawn dashed as "revealed later", (c) the forecast made 3 h earlier
  const prevOrigin = iso(o0 - 3 * 60 * Q / 15);
  const prevRows = ix.origins.includes(prevOrigin) ? ix.get(prevOrigin) : [];
  const prevAt = new Map(prevRows.map((r) => [r.delivery_start_utc, r]));
  const lastKnownMs = o0 - 75 * 60 * 1000;
  const past = [];
  for (let k = 12; k >= 1; k--) {
    const ms = o0 - k * Q, key = iso(ms), pr = prevAt.get(key);
    past.push({ key, t: hhmm(key),
      pastActual: ms <= lastKnownMs ? (actualAt.get(key) ?? null) : null,
      pastLater: ms >= lastKnownMs ? (actualAt.get(key) ?? null) : null,
      prevBase: pr ? pr.p10 : null, prevWidth: pr ? pr.p90 - pr.p10 : null, prevP50: pr ? pr.p50 : null });
  }
  const chart = [...past, ...rows.map((r) => ({ key: r.delivery_start_utc, t: hhmm(r.delivery_start_utc), base: r.p10, width: r.p90 - r.p10, p10: r.p10, p50: r.p50, p90: r.p90,
    actual: hasAct ? r.actual_imbalance_price : null }))];
  const withAct = rows.filter((r) => hasAct && r.actual_imbalance_price != null);
  const mae = withAct.length ? withAct.reduce((s, r) => s + Math.abs(r.p50 - r.actual_imbalance_price), 0) / withAct.length : null;
  const cov = withAct.length ? withAct.filter((r) => r.actual_imbalance_price >= r.p10 && r.actual_imbalance_price <= r.p90).length / withAct.length : null;
  const maxHi = Math.max(...rows.map((r) => r.p_spike_high)); const maxLo = Math.max(...rows.map((r) => r.p_spike_low));
  const upShare = rows.reduce((s, r) => s + r.p_up, 0) / rows.length;
  const hiRow = rows.reduce((a, r) => (r.p_spike_high > a.p_spike_high ? r : a), rows[0]);
  const drivers = (rows[0].top_drivers || "").split(";").filter(Boolean);

  const dirText = upShare > 0.55 ? "Up-regulation more likely (price above spot)" : upShare < 0.45 ? "Down-regulation more likely (price below spot)" : "Direction is uncertain";
  const lo50 = Math.round(Math.min(...rows.map((r) => r.p50))), hi50 = Math.round(Math.max(...rows.map((r) => r.p50)));
  const summary = `${dirText}. Median ${lo50} to ${hi50} EUR/MWh. ` +
    (maxHi >= 0.3 ? `High-spike risk peaks at ${(maxHi * 100).toFixed(0)}% around ${hhmm(hiRow.delivery_start_utc)}.` : "No elevated spike risk.");
  const stat = "[&>span:nth-child(2)]:text-3xl";

  return shell(
    <>
      {header}
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[17rem_1fr]">
        {/* left: the key numbers, short summary, drivers */}
        <aside className="flex min-h-0 flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            {hasAct && <Card className="bg-card/90 p-3 backdrop-blur"><Stat className={stat} label="Error p50" value={mae == null ? "–" : mae.toFixed(1)} unit="€" /></Card>}
            {hasAct && <Card className="bg-card/90 p-3 backdrop-blur"><Stat className={stat} label="In band" value={cov == null ? "–" : (cov * 100).toFixed(0) + "%"} /></Card>}
            <Card className="bg-card/90 p-3 backdrop-blur"><Stat className={stat} label="P(high spike)" value={(maxHi * 100).toFixed(0) + "%"} trend={maxHi >= 0.3 ? "up" : "neutral"} /></Card>
            <Card className="bg-card/90 p-3 backdrop-blur"><Stat className={stat} label="P(low spike)" value={(maxLo * 100).toFixed(0) + "%"} /></Card>
            <Card className="col-span-2 bg-card/90 p-3 backdrop-blur"><Stat className={stat} label="P(up-regulation)" value={(upShare * 100).toFixed(0) + "%"} /></Card>
          </div>
          <Alert variant={maxHi >= 0.3 || maxLo >= 0.4 ? "warning" : "info"} className="p-3">
            <div><AlertTitle className="text-xs">Summary</AlertTitle><p className="mt-1 leading-snug">{summary}</p></div>
          </Alert>
          <Card className="min-h-0 flex-1 overflow-auto bg-card/90 p-3 backdrop-blur">
            <p className="font-display text-xs font-bold uppercase tracking-wide text-muted-foreground">What drives this forecast</p>
            <ol className="mt-2 space-y-2">
              {drivers.map((x, i) => (
                <li key={x} className="flex items-start gap-2 text-sm"><Badge variant="primary">{i + 1}</Badge><span className="leading-snug">{HELP[x] || x.replaceAll("_", " ")}</span></li>
              ))}
            </ol>
          </Card>
        </aside>

        {/* right: the chart, as big as possible, with the time controls above it */}
        <Card className="flex min-h-[26rem] flex-col bg-card/95 p-4 backdrop-blur">
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => step(-24)}>◀ 1 day</Button>
            <Button size="sm" variant="outline" onClick={() => step(-1)}>◀ 1 h</Button>
            <select aria-label="date" className={selectCls} value={dayOf(origin)} onChange={(e) => { const o = ix.origins.find((x) => dayOf(x) === e.target.value); if (o) setOrigin(o); }}>
              {days.map((dd) => <option key={dd} value={dd}>{isoDayToFi(dd)}</option>)}
            </select>
            <input type="range" aria-label="whole period" className="min-w-32 flex-1 accent-primary" min={0} max={ix.origins.length - 1} value={pos} onChange={(e) => setOrigin(ix.origins[+e.target.value])} />
            <b data-testid="when" className="font-display text-lg">{mdOf(origin)} {hhmm(origin)}</b>
            <Button size="sm" variant="outline" onClick={() => step(1)}>1 h ▶</Button>
            <Button size="sm" variant="outline" onClick={() => step(24)}>1 day ▶</Button>
          </div>
          <div className="mt-2 min-h-72 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chart} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="key" interval={3} tickFormatter={hhmm} stroke={C.axis} fontSize={12} />
                <YAxis stroke={C.axis} fontSize={12} unit=" €" width={56} />
                <Tooltip contentStyle={tip} labelFormatter={(l) => `${mdOf(l)} ${hhmm(l)}`} />
                <Area dataKey="prevBase" stackId="c" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                <Area dataKey="prevWidth" stackId="c" stroke="none" fill={C.earlier} fillOpacity={0.18} name="earlier forecast band" isAnimationActive={false} />
                <Line dataKey="prevP50" stroke={C.earlier} strokeWidth={2} strokeDasharray="2 3" dot={false} name="earlier forecast (3 h before)" isAnimationActive={false} />
                <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                <Area dataKey="width" stackId="b" stroke="none" fill={C.band} fillOpacity={0.35} name="p10–p90 band" isAnimationActive={false} />
                <Line dataKey="p50" stroke={C.p50} strokeWidth={3} dot={false} name="forecast p50" isAnimationActive={false} />
                {hasAct && <Line dataKey="pastActual" stroke={C.actual} strokeWidth={2} dot={false} connectNulls name="actual price (known then)" isAnimationActive={false} />}
                {hasAct && <Line dataKey="actual" stroke={C.actual} strokeDasharray="5 3" strokeWidth={2} dot={false} name="actual price (revealed later)" isAnimationActive={false} />}
                {hasAct && <Line dataKey="pastLater" stroke={C.actual} strokeDasharray="5 3" strokeWidth={2} dot={false} connectNulls legendType="none" isAnimationActive={false} />}
                <ReferenceLine x={rows[0].delivery_start_utc} stroke={C.now} strokeWidth={2} label={{ value: "now", position: "insideTopLeft", fill: "var(--foreground)", fontSize: 12 }} />
                <ReferenceLine y={0} stroke={C.axis} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Gap before "now": prices are published about 1 h after each quarter-hour, so at {hhmm(origin)} the latest known price starts {hhmm(iso(o0 - 75 * 60 * 1000))}; the forecast starts one hour blind.
          </p>
        </Card>
      </div>
    </>
  );
}
