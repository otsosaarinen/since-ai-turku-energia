"""Tests for src/live_alerts.py: the live feeds are turned into alerts only when they can move the price."""
from src.live_alerts import collect

MET = {"features": [{"properties": {
    "id": "2.49.0.1.246.0.20261107153000.001", "title": "Yellow warning for wind in Varsinais-Suomi",
    "event": "wind", "awareness_level": "2; yellow; Moderate", "severity": "Moderate",
    "description": "Strong wind gusts 15-20 m/s.", "onset": "2026-11-07T18:00:00+00:00",
    "expires": "2026-11-08T06:00:00+00:00", "area": "Varsinais-Suomi",
}}]}

GDACS = {"features": [
    {"properties": {"eventid": 1, "name": "Forest fires in Nigeria", "alertlevel": "Green", "country": "Nigeria"}},
    {"properties": {"eventid": 2, "name": "Storm in Finland", "alertlevel": "Orange", "country": "Finland",
                    "fromdate": "2026-11-07T12:00:00", "todate": "2026-11-08T12:00:00"}},
]}

CARUNA = {"outages": [
    {"id": "INC 1", "type": "OUTAGE", "size": 1, "startTime": "2026-11-07T15:21:00Z", "estimatedEndTime": "2026-11-07T19:30:00Z",
     "municipality": {"name": {"en": "Sauvo"}}},
    {"id": "INC 2", "type": "OUTAGE", "size": 250, "startTime": "2026-11-07T15:21:00Z", "estimatedEndTime": "2026-11-07T19:30:00Z",
     "municipality": {"name": {"en": "Turku"}}},
]}

WIND = {"hourly": {"time": ["2026-11-07T00:00", "2026-11-07T01:00"], "wind_speed_10m": [1.0, 2.0]}}


def test_collect_keeps_only_price_relevant_alerts():
    alerts = collect(MET, GDACS, WIND, CARUNA)
    ids = {a["id"] for a in alerts}
    assert ids == {"met:2.49.0.1.246.0.20261107153000.001", "gdacs:2", "outage:INC 2"}
    assert "gdacs:1" not in ids          # Nigeria cannot move the Finnish price
    assert "outage:INC 1" not in ids     # one customer is noise


def test_severity_and_text():
    by_id = {a["id"]: a for a in collect(MET, GDACS, WIND, CARUNA)}
    assert by_id["met:2.49.0.1.246.0.20261107153000.001"]["severity"] == "yellow"
    assert by_id["met:2.49.0.1.246.0.20261107153000.001"]["until"] == "2026-11-08T06:00:00+00:00"
    assert by_id["gdacs:2"]["severity"] == "orange"
    assert "250 customers" in by_id["outage:INC 2"]["title"]


def test_a_dead_feed_does_not_hide_the_others():
    assert {a["id"] for a in collect({}, {}, {}, CARUNA)} == {"outage:INC 2"}


def test_wind_shift_needs_enough_hours():
    # 2 hours is not enough to compare 12 h behind with 12 h ahead
    assert collect({}, {}, WIND, {}) == []
