"""Small local viewer: uv run --group app streamlit run app/app.py"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Validation (7 Sep - 4 Oct, has actual prices)": ROOT / "outputs/validation/backtest_vs_actual.csv",
    "Final test forecast (5 Oct - 1 Nov, no actuals)": ROOT / "outputs/final/forecast_backtest.csv",
}

st.set_page_config(page_title="Imbalance price forecast", layout="wide")
st.title("Imbalance price forecast, 10 h ahead")
src = st.sidebar.radio("Forecast set", list(SOURCES))


@st.cache_data
def load(path):
    d = pd.read_csv(path)
    for c in ("forecast_origin_utc", "delivery_start_utc"):
        d[c] = pd.to_datetime(d[c], utc=True)
    return d


path = SOURCES[src]
if not path.exists():
    st.error(f"{path.name} not found. Run scripts/run_validation.py / run_final.py first.")
    st.stop()
d = load(path)
origins = sorted(d.forecast_origin_utc.unique())
lo, hi = pd.Timestamp(origins[0]), pd.Timestamp(origins[-1])
day = st.sidebar.date_input("Date (UTC)", value=lo.date(), min_value=lo.date(), max_value=hi.date())
hours = [pd.Timestamp(o) for o in origins if pd.Timestamp(o).date() == day]
if not hours:
    st.warning("No origins on that date.")
    st.stop()
o = st.sidebar.select_slider("Forecast origin (UTC hour)", options=hours, value=hours[0], format_func=lambda t: f"{t:%H:%M}")
x = d[d.forecast_origin_utc == o].sort_values("step")
has_actual = "actual_imbalance_price" in x

c1, c2, c3, c4 = st.columns(4)
if has_actual:
    c1.metric("MAE of p50 (this origin)", f"{x.abs_error_p50.mean():.1f} EUR/MWh")
    c2.metric("Actual inside p10-p90", f"{x.inside_p10_p90.mean():.0%}")
c3.metric("Max P(high spike)", f"{x.p_spike_high.max():.2f}")
c4.metric("Max P(low spike)", f"{x.p_spike_low.max():.2f}")

base = alt.Chart(x).encode(x=alt.X("delivery_start_utc:T", title="Delivery quarter-hour (UTC)"))
band = base.mark_area(opacity=0.25).encode(y="p10:Q", y2="p90:Q")
p50 = base.mark_line(strokeWidth=2).encode(y=alt.Y("p50:Q", title="EUR/MWh"))
layers = band + p50
if has_actual:
    layers += base.mark_line(color="red", strokeDash=[4, 3]).encode(y="actual_imbalance_price:Q")
st.altair_chart(layers.properties(height=350), width="stretch")
st.caption("Line = p50, shaded = p10-p90" + (", red dashed = actual price." if has_actual else "."))

left, right = st.columns(2)
prob = x.melt("delivery_start_utc", ["p_up", "p_down", "p_spike_high", "p_spike_low"], "probability", "value")
left.subheader("Probabilities")
left.altair_chart(alt.Chart(prob).mark_line().encode(x="delivery_start_utc:T", y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1])),
                                                     color="probability:N").properties(height=250), width="stretch")
right.subheader("What drives this forecast")
right.write(x.top_drivers.iloc[0].replace(";", "  \n"))
right.write(f"Data cut-off: {x.data_cutoff_utc.iloc[0]}")
with st.expander("Table"):
    st.dataframe(x.drop(columns=["top_drivers"]).round(2))
