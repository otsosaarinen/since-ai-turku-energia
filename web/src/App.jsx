import React, { useEffect, useMemo, useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const SETS = { validation: "Validation 7 Sep – 4 Oct (with actuals)", final: "Test forecast 5 Oct – 1 Nov" };
const HELP = {
  spot_price: "the day-ahead spot price", consumption_forecast_da: "the day-ahead consumption forecast",
  wind_forecast_da: "the wind power forecast", solar_forecast_da: "the solar power forecast",
  residual_load_forecast: "residual load (consumption minus wind and solar)", latest_imbalance_price: "the latest imbalance prices",
  imbalance_minus_spot_history: "recent imbalance prices relative to spot", mfrr_direction_history: "the recent regulation direction",
  mfrr_prices_and_activation: "mFRR prices and activations", afrr_activity: "aFRR activity", cross_border_flows: "cross-border flows",
  neighbour_imbalance_prices: "neighbouring-area imbalance prices", same_time_previous_days_imbalance: "the imbalance price at the same time on previous days",
  consumption_actual: "measured consumption", production_actual: "measured production", neighbour_load_forecasts: "neighbouring-area load forecasts", fi_ee_capacity: "the Finland–Estonia transfer capacity", calendar: "time of day and weekday", forecast_horizon: "how far ahead",
};
// Data is stored in UTC; everything shown on the page is Finnish time (Europe/Helsinki, incl. the 25 Oct clock change).
const FI = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Helsinki", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const fiParts = (t) => Object.fromEntries(FI.formatToParts(new Date(t)).map((p) => [p.type, p.value]));
const hhmm = (t) => { const p = fiParts(t); return `${p.hour}:${p.minute}`; };
const mdOf = (t) => { const p = fiParts(t); return `${p.day}.${p.month}.`; };
const dayOf = (t) => { const p = fiParts(t); return `${p.year}-${p.month}-${p.day}`; };

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
  // hindsight: daily MAE / coverage over the whole set (validation only)
  const daily = useMemo(() => {
    if (!d || !ix || !d.hasActuals) return [];
    const m = new Map();
    for (const o of ix.origins) for (const r of ix.get(o)) {
      if (r.actual_imbalance_price == null) continue;
      const k = dayOf(r.forecast_origin_utc); const e = m.get(k) || { n: 0, ae: 0, in: 0 };
      e.n++; e.ae += Math.abs(r.p50 - r.actual_imbalance_price); e.in += r.actual_imbalance_price >= r.p10 && r.actual_imbalance_price <= r.p90 ? 1 : 0; m.set(k, e);
    }
    return [...m].map(([day, e]) => ({ day: day.slice(8) + "." + day.slice(5, 7) + ".", mae: +(e.ae / e.n).toFixed(1), cov: +(e.in / e.n * 100).toFixed(0) }));
  }, [ix, d]);

  const actualAt = useMemo(() => {
    const m = new Map();
    if (!d || !d.hasActuals) return m;
    const ti = d.cols.indexOf("delivery_start_utc"), ai = d.cols.indexOf("actual_imbalance_price");
    for (const r of d.rows) if (r[ai] != null) m.set(r[ti], r[ai]);
    return m;
  }, [d]);
  if (err) return <div className="card" style={{ margin: 24 }}>Could not load /data/{set}.json ({err}). Run <code>uv run scripts/export_web_data.py</code> first.</div>;
  if (!ix || !origin || !ix.origins.includes(origin)) return <div style={{ padding: 24 }}>Loading…</div>;

  const rows = ix.get(origin);
  const hasAct = d.hasActuals;
  const days = [...new Set(ix.origins.map(dayOf))];
  const hoursOfDay = ix.origins.filter((o) => dayOf(o) === dayOf(origin));
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
    actual: hasAct ? r.actual_imbalance_price : null, up: r.p_up, down: r.p_down, hi: r.p_spike_high, lo: r.p_spike_low }))];
  const probs = chart.filter((c) => c.p50 != null);
  const withAct = rows.filter((r) => hasAct && r.actual_imbalance_price != null);
  const mae = withAct.length ? withAct.reduce((s, r) => s + Math.abs(r.p50 - r.actual_imbalance_price), 0) / withAct.length : null;
  const cov = withAct.length ? withAct.filter((r) => r.actual_imbalance_price >= r.p10 && r.actual_imbalance_price <= r.p90).length / withAct.length : null;
  const maxHi = Math.max(...rows.map((r) => r.p_spike_high)); const maxLo = Math.max(...rows.map((r) => r.p_spike_low));
  const upShare = rows.reduce((s, r) => s + r.p_up, 0) / rows.length;
  const hiRow = rows.reduce((a, r) => (r.p_spike_high > a.p_spike_high ? r : a), rows[0]);
  const drivers = (rows[0].top_drivers || "").split(";").filter(Boolean);

  const dirText = upShare > 0.55 ? "up-regulation more likely (price above spot)" : upShare < 0.45 ? "down-regulation more likely (price below spot)" : "direction is uncertain";
  const summary = `From ${hhmm(origin)} (Finnish time) the model expects ${dirText}. Median ${Math.round(Math.min(...rows.map(r => r.p50)))}–${Math.round(Math.max(...rows.map(r => r.p50)))} EUR/MWh; ` +
    (maxHi >= 0.3 ? `high-spike risk peaks at ${(maxHi * 100).toFixed(0)}% around ${hhmm(hiRow.delivery_start_utc)}. ` : "no elevated spike risk. ") +
    (drivers.length ? `Main drivers: ${drivers.map((x) => HELP[x] || x).join(", ")}.` : "");

  return (
    <>
      <header>
        <h1>Imbalance price forecast · 10 h ahead</h1>
        <div className="tabs">{Object.entries(SETS).map(([k, v]) => <button key={k} className={set === k ? "on" : ""} onClick={() => setSet(k)}>{v}</button>)}</div>
      </header>
      <div className="layout">
        <main>
          <div className="card">
            <h2>Review point (Finnish time) — move it into the past or forward</h2>
            <div className="controls nav">
              <button onClick={() => step(-24)}>◀ −1 day</button>
              <button onClick={() => step(-1)}>◀ −1 h</button>
              <input type="date" value={dayOf(origin)} min={days[0]} max={days[days.length - 1]} aria-label="date"
                onChange={(e) => { const o = ix.origins.find((x) => dayOf(x) === e.target.value); if (o) setOrigin(o); }} />
              <input type="range" aria-label="whole period" min={0} max={ix.origins.length - 1} value={pos} onChange={(e) => setOrigin(ix.origins[+e.target.value])} />
              <b data-testid="when">{mdOf(origin)} {hhmm(origin)}</b>
              <button onClick={() => step(1)}>+1 h ▶</button>
              <button onClick={() => step(24)}>+1 day ▶</button>
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>The bar covers the whole period ({mdOf(ix.origins[0])} – {mdOf(ix.origins[ix.origins.length - 1])}); the date box jumps to a day.</div>
          </div>
          <div className="card"><h2>Summary</h2><div className="msg">{summary}</div></div>
          <div className="kpis card">
            {hasAct && <div className="kpi"><b>{mae == null ? "–" : mae.toFixed(1)}</b><span>MAE of p50 (EUR/MWh)</span></div>}
            {hasAct && <div className="kpi"><b>{cov == null ? "–" : (cov * 100).toFixed(0) + "%"}</b><span>actual inside p10–p90</span></div>}
            <div className="kpi"><b>{(maxHi * 100).toFixed(0)}%</b><span>max P(high spike)</span></div>
            <div className="kpi"><b>{(maxLo * 100).toFixed(0)}%</b><span>max P(low spike)</span></div>
            <div className="kpi"><b>{(upShare * 100).toFixed(0)}%</b><span>avg P(up-regulation)</span></div>
          </div>
          <div className="card">
            <h2>Price forecast, EUR/MWh (shaded = p10–p90)</h2>
            <div className="muted" style={{ marginBottom: 6 }}>Left of the vertical line is the past: only prices already published at the forecast origin are drawn (publication takes about 1 h, so the last hour is unknown).</div>
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={chart}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" /><XAxis dataKey="key" interval={3} tickFormatter={hhmm} stroke="var(--mute)" /><YAxis stroke="var(--mute)" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} />
                <Area dataKey="prevBase" stackId="c" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                <Area dataKey="prevWidth" stackId="c" stroke="none" fill="var(--mute)" fillOpacity={0.2} name="earlier forecast p10–p90" isAnimationActive={false} />
                <Line dataKey="prevP50" stroke="var(--mute)" strokeWidth={2} strokeDasharray="2 3" dot={false} name="earlier forecast p50 (made 3 h before)" isAnimationActive={false} />
                <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                <Area dataKey="width" stackId="b" stroke="none" fill="var(--band)" fillOpacity={0.5} name="p10–p90 band" isAnimationActive={false} />
                <Line dataKey="p50" stroke="var(--accent)" strokeWidth={2} dot={false} name="p50" isAnimationActive={false} />
                {hasAct && <Line dataKey="pastActual" stroke="var(--bad)" strokeWidth={2} dot={false} connectNulls name="actual (known at origin)" isAnimationActive={false} />}
                {hasAct && <Line dataKey="actual" stroke="var(--bad)" strokeDasharray="5 3" dot={false} name="actual (revealed later)" isAnimationActive={false} />}
                {hasAct && <Line dataKey="pastLater" stroke="var(--bad)" strokeDasharray="5 3" dot={false} connectNulls legendType="none" isAnimationActive={false} />}
                <ReferenceLine x={rows[0].delivery_start_utc} stroke="var(--ink)" strokeWidth={2} label={{ value: "now (forecast origin)", position: "insideTopLeft", fill: "var(--ink)", fontSize: 12 }} />
                <ReferenceLine y={0} stroke="var(--mute)" /><Legend />
              </ComposedChart>
            </ResponsiveContainer>
            <div className="note">
              <b>Why is there a gap before "now"?</b> A price is published about 1 hour after its quarter-hour ends. At {hhmm(origin)} the latest price the model can see is the one
              starting {hhmm(iso(o0 - 75 * 60 * 1000))}. The prices for {hhmm(iso(o0 - 60 * 60 * 1000))}–{hhmm(origin)} exist, but were not public yet, so the model
              (and the chart) cannot use them. The forecast therefore starts one hour "blind".
              {prevRows.length > 0 && <> <b>Grey</b> = the forecast made 3 hours earlier for these same hours, so you can see how it compared with what really happened.</>}
            </div>

          </div>
          <div className="card">
            <h2>Probabilities per quarter-hour</h2>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={probs}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" /><XAxis dataKey="t" interval={3} stroke="var(--mute)" /><YAxis domain={[0, 1]} stroke="var(--mute)" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} /><Legend />
                <Line dataKey="up" stroke="#16a34a" dot={false} name="P(up)" isAnimationActive={false} />
                <Line dataKey="down" stroke="#7c3aed" dot={false} name="P(down)" isAnimationActive={false} />
                <Line dataKey="hi" stroke="#dc2626" dot={false} name="P(high spike)" isAnimationActive={false} />
                <Line dataKey="lo" stroke="#d97706" dot={false} name="P(low spike)" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="card">
            <h2>What drives this forecast</h2>
            <ol className="drivers">{drivers.map((x) => <li key={x}><b>{x.replaceAll("_", " ")}</b> <span className="muted">— {HELP[x] || ""}</span></li>)}</ol>
            <div className="muted">Forecast made at {dayOf(origin)} {hhmm(origin)} Finnish time, using only data published by that time.</div>
          </div>
          {hasAct && (
            <div className="card">
              <h2>How the forecast performed in hindsight — MAE per day (EUR/MWh)</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={daily}><CartesianGrid stroke="var(--line)" strokeDasharray="3 3" /><XAxis dataKey="day" stroke="var(--mute)" /><YAxis stroke="var(--mute)" />
                  <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} /><Bar dataKey="mae" fill="var(--accent)" name="MAE" isAnimationActive={false} /></BarChart>
              </ResponsiveContainer>
            </div>)}
        </main>
      </div>
    </>
  );
}
