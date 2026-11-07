import pandas as pd

from src.alerts import evaluate_origin_alerts, generate_situational_overview


def _make_dummy_origin(origin="2026-10-15T00:00:00Z", high_spike_val=0.10, low_spike_val=0.05, p_up=0.33):
    times = pd.date_range("2026-10-15T00:00:00Z", periods=40, freq="15min")
    return pd.DataFrame(
        {
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
        }
    )


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


def test_alert_fields_and_values_for_a_high_spike():
    df = _make_dummy_origin(origin="2026-10-15T00:00:00Z", high_spike_val=0.25, p_up=0.5)
    df.loc[3, "p_spike_high"] = 0.30
    df.loc[3, "p50"] = 99.0
    (alert,) = evaluate_origin_alerts(df)
    assert list(alert) == [
        "origin_utc",
        "type",
        "severity",
        "time_window",
        "max_p_spike",
        "expected_price",
        "drivers",
        "recommendation",
    ]
    assert alert["origin_utc"] == "2026-10-15T00:00:00Z" and alert["time_window"] == "00:00 - 09:45 UTC"
    assert (
        alert["max_p_spike"] == 0.3
        and alert["expected_price"] == 99.0
        and alert["drivers"] == "spot_price;wind_forecast_da"
    )


def test_low_spike_reports_the_lowest_expected_price():
    df = _make_dummy_origin(low_spike_val=0.25, p_up=0.5)
    df.loc[5, "p50"] = -20.0
    (alert,) = evaluate_origin_alerts(df)
    assert alert["type"] == "LOW_SPIKE_RISK" and alert["expected_price"] == -20.0


def test_regime_alerts_up_before_down_and_only_above_55_percent():
    up = evaluate_origin_alerts(_make_dummy_origin(p_up=0.60))
    assert (
        [a["type"] for a in up] == ["REGULATION_REGIME_UP"]
        and up[0]["severity"] == "MEDIUM"
        and up[0]["max_p_spike"] == 0.0
    )
    down = evaluate_origin_alerts(_make_dummy_origin(p_up=0.30))  # p_down = 0.70
    assert [a["type"] for a in down] == ["REGULATION_REGIME_DOWN"] and down[0]["time_window"] == "Across 10h horizon"
    assert evaluate_origin_alerts(_make_dummy_origin(p_up=0.50)) == []


def test_missing_optional_columns_do_not_break_the_alerts():
    df = _make_dummy_origin(high_spike_val=0.25).drop(columns=["top_drivers", "p_up", "p_down"])
    (alert,) = evaluate_origin_alerts(df)
    assert alert["drivers"] == ""
    assert evaluate_origin_alerts(df.iloc[0:0]) == []


def test_text_timestamps_work_and_recent_origins_limits_the_scan():
    frames = [_make_dummy_origin(origin=f"2026-10-15T0{hour}:00:00Z", high_spike_val=0.3) for hour in range(3)]
    combined = pd.concat(frames, ignore_index=True)
    combined["delivery_start_utc"] = combined["delivery_start_utc"].dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )  # as in the CSV export
    assert len([a for a in generate_situational_overview(combined) if a["type"] == "HIGH_SPIKE_RISK"]) == 3
    latest = [a for a in generate_situational_overview(combined, recent_origins=1) if a["type"] == "HIGH_SPIKE_RISK"]
    assert [a["origin_utc"] for a in latest] == ["2026-10-15T02:00:00Z"]
    assert not pd.api.types.is_datetime64_any_dtype(combined["delivery_start_utc"])  # the caller's frame is unchanged
