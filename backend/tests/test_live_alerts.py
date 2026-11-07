"""Tests for src/live_alerts.py: the live feeds are turned into alerts only when they can move the price."""

import json
from datetime import UTC, datetime, timedelta

from src import live_alerts
from src.live_alerts import collect

MET = {
    "features": [
        {
            "properties": {
                "id": "2.49.0.1.246.0.20261107153000.001",
                "title": "Yellow warning for wind in Varsinais-Suomi",
                "event": "wind",
                "awareness_level": "2; yellow; Moderate",
                "severity": "Moderate",
                "description": "Strong wind gusts 15-20 m/s.",
                "onset": "2026-11-07T18:00:00+00:00",
                "expires": "2026-11-08T06:00:00+00:00",
                "area": "Varsinais-Suomi",
            }
        }
    ]
}

GDACS = {
    "features": [
        {"properties": {"eventid": 1, "name": "Forest fires in Nigeria", "alertlevel": "Green", "country": "Nigeria"}},
        {
            "properties": {
                "eventid": 2,
                "name": "Storm in Finland",
                "alertlevel": "Orange",
                "country": "Finland",
                "fromdate": "2026-11-07T12:00:00",
                "todate": "2026-11-08T12:00:00",
            }
        },
    ]
}

CARUNA = {
    "outages": [
        {
            "id": "INC 1",
            "type": "OUTAGE",
            "size": 1,
            "startTime": "2026-11-07T15:21:00Z",
            "estimatedEndTime": "2026-11-07T19:30:00Z",
            "municipality": {"name": {"en": "Sauvo"}},
        },
        {
            "id": "INC 2",
            "type": "OUTAGE",
            "size": 250,
            "startTime": "2026-11-07T15:21:00Z",
            "estimatedEndTime": "2026-11-07T19:30:00Z",
            "municipality": {"name": {"en": "Turku"}},
        },
    ]
}

WIND = {"hourly": {"time": ["2026-11-07T00:00", "2026-11-07T01:00"], "wind_speed_10m": [1.0, 2.0]}}


def test_collect_keeps_only_price_relevant_alerts():
    alerts = collect(MET, GDACS, WIND, CARUNA)
    ids = {a["id"] for a in alerts}
    assert ids == {"met:2.49.0.1.246.0.20261107153000.001", "gdacs:2", "outage:INC 2"}
    assert "gdacs:1" not in ids  # Nigeria cannot move the Finnish price
    assert "outage:INC 1" not in ids  # one customer is noise


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


def _wind_feed(before: float, after: float) -> dict:
    """48 hourly values: 12 h before the current hour at `before`, the rest from the current hour at `after`."""
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    times = [(start + timedelta(hours=n)).strftime("%Y-%m-%dT%H:00") for n in range(48)]
    speeds = [before if n < 24 else after for n in range(48)]
    return {"hourly": {"time": times, "wind_speed_10m": speeds}}


def test_a_big_wind_shift_gives_one_alert_with_a_stable_id():
    (alert,) = collect({}, {}, _wind_feed(2.0, 8.0), {})
    assert alert["id"] == "wind:up" and alert["severity"] == "high" and "+6.0 m/s" in alert["title"]
    (calm,) = collect({}, {}, _wind_feed(9.0, 5.0), {})
    assert calm["id"] == "wind:down" and calm["severity"] == "moderate"
    assert collect({}, {}, _wind_feed(5.0, 6.0), {}) == []  # a 1 m/s change is not news


def test_garbled_feeds_are_ignored_instead_of_crashing():
    garbage = {
        "features": ["text", 5, None, {"properties": "oops"}, {"properties": {"country": "Finland", "eventid": 9}}]
    }
    alerts = collect(
        garbage,
        garbage,
        {"hourly": "x"},
        {"outages": [None, {"size": "many"}, {"size": True}, {"size": 50, "municipality": "x"}]},
    )
    assert [a["id"] for a in alerts] == ["met:None", "met:None", "gdacs:9", "outage:None"]
    assert [a for a in alerts if a["kind"] == "outage"][0]["title"].endswith("?, 50 customers")
    assert collect(None, None, None, None) == []


def test_a_wind_feed_with_nulls_gives_no_alert_instead_of_an_error():
    feed = _wind_feed(2.0, 8.0)
    feed["hourly"]["wind_speed_10m"][30] = None
    assert collect({}, {}, feed, {}) == []


def test_alert_text_from_the_internet_is_shortened():
    huge = "x" * 5000
    met = {"features": [{"properties": {"id": huge, "title": huge, "description": huge, "onset": huge}}]}
    (alert,) = collect(met, {}, {}, {})
    assert len(alert["title"]) == live_alerts.TITLE_CHARS and len(alert["detail"]) == live_alerts.DETAIL_CHARS
    assert len(alert["id"]) <= live_alerts.ID_CHARS + 4 and len(alert["at"]) == live_alerts.ID_CHARS


class _Response:
    def __init__(self, body: bytes):
        self._body = body
        self.headers = type("H", (), {"get_content_charset": staticmethod(lambda: None)})()

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_dead_or_garbled_feed_gives_an_empty_dict_and_a_log_line(monkeypatch, caplog):
    def broken(request, timeout):
        raise OSError("network down")

    monkeypatch.setattr(live_alerts.urllib.request, "urlopen", broken)
    assert live_alerts._safe("https://example.invalid/feed?x=1") == {}
    assert "alert feed unavailable" in caplog.text and "x=1" not in caplog.text  # the query part is not logged
    monkeypatch.setattr(live_alerts.urllib.request, "urlopen", lambda request, timeout: _Response(b"[1, 2]"))
    assert live_alerts._safe("https://example.invalid/") == {}  # valid JSON but not an object
    monkeypatch.setattr(live_alerts.urllib.request, "urlopen", lambda request, timeout: _Response(b"not json"))
    assert live_alerts._safe("https://example.invalid/") == {}


def test_fetch_asks_the_four_feeds_with_a_timeout_and_a_user_agent(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request.full_url, request.get_header("User-agent"), timeout))
        return _Response(json.dumps(CARUNA).encode() if "caruna" in request.full_url else b"{}")

    monkeypatch.setattr(live_alerts.urllib.request, "urlopen", fake_urlopen)
    alerts = live_alerts.fetch()
    assert [a["id"] for a in alerts] == ["outage:INC 2"]
    assert len(seen) == 4 and all(url.startswith("https://") for url, _, _ in seen)
    assert all(
        agent == live_alerts.USER_AGENT and timeout == live_alerts.REQUEST_TIMEOUT_S for _, agent, timeout in seen
    )
    assert {url.split("/")[2] for url, _, _ in seen} == {
        "api.met.no",
        "www.gdacs.org",
        "plus.caruna.fi",
        "api.open-meteo.com",
    }
