import numpy as np
import pandas as pd
from src.alerts import (
    evaluate_origin_alerts,
    generate_situational_overview,
    HIGH_SPIKE_THRESHOLD,
    HIGH_SPIKE_CRITICAL,
    LOW_SPIKE_THRESHOLD,
)


def _make_dummy_origin(origin="2026-10-15T00:00:00Z", high_spike_val=0.10, low_spike_val=0.05, p_up=0.33):
    times = pd.date_range("2026-10-15T00:00:00Z", periods=40, freq="15min")
    return pd.DataFrame({
        "forecast_origin_utc": [origin] * 40,
        "delivery_start_utc": times,
        "step": list(range(1, 41)),
        "p10": [20.0] * 40,
        "p50": [45.0] * 40,
        "p90": [70.0] * 40,
        "p_up": [p_up] * 40,
        "p_down": [1.0 - p_up] * 40,
        "p_none": [0.0] * 40,
        "p_spike_high": [high_spike_val] * 40,
        "p_spike_low": [low_spike_val] * 40,
        "top_drivers": ["spot_price;wind_forecast_da"] * 40,
    })


def test_no_alerts_under_threshold():
    df = _make_dummy_origin(high_spike_val=0.05, low_spike_val=0.05, p_up=0.45)
    alerts = evaluate_origin_alerts(df)
    assert len(alerts) == 0


def test_high_spike_alert_high_severity():
    df = _make_dummy_origin(high_spike_val=0.25, low_spike_val=0.05)
    alerts = evaluate_origin_alerts(df)
    spike_alerts = [a for a in alerts if a["type"] == "HIGH_SPIKE_RISK"]
    assert len(spike_alerts) == 1
    assert spike_alerts[0]["severity"] == "HIGH"
    assert spike_alerts[0]["max_p_spike"] == 0.25
    assert "Review thermal dispatch plan" in spike_alerts[0]["recommendation"]


def test_high_spike_alert_critical_severity():
    df = _make_dummy_origin(high_spike_val=0.40, low_spike_val=0.05)
    alerts = evaluate_origin_alerts(df)
    spike_alerts = [a for a in alerts if a["type"] == "HIGH_SPIKE_RISK"]
    assert len(spike_alerts) == 1
    assert spike_alerts[0]["severity"] == "CRITICAL"
    assert spike_alerts[0]["max_p_spike"] == 0.40


def test_low_spike_alert():
    df = _make_dummy_origin(high_spike_val=0.05, low_spike_val=0.28)
    alerts = evaluate_origin_alerts(df)
    low_alerts = [a for a in alerts if a["type"] == "LOW_SPIKE_RISK"]
    assert len(low_alerts) == 1
    assert low_alerts[0]["severity"] == "HIGH"
    assert low_alerts[0]["max_p_spike"] == 0.28
    assert "Downward regulation dominant" in low_alerts[0]["recommendation"]


def test_generate_situational_overview():
    df1 = _make_dummy_origin(origin="2026-10-15T00:00:00Z", high_spike_val=0.30)
    df2 = _make_dummy_origin(origin="2026-10-15T01:00:00Z", low_spike_val=0.25)
    combined = pd.concat([df1, df2], ignore_index=True)
    all_alerts = generate_situational_overview(combined)
    assert len(all_alerts) >= 2
