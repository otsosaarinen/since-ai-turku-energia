"""Live alerts that can move the Finnish imbalance price.

Three keyless feeds (MET Norway weather warnings, GDACS disasters, Caruna network outages) plus the Open-Meteo wind
forecast, parsed into one short list. `collect` is pure (it takes the parsed JSON); `fetch` is the network layer,
called by the harness server (backend/harness/watcher.py), which reruns the forecast when a new alert id appears.

Feed content is untrusted text from the internet: it is only shown on the website (which escapes it) and is never handed
to the model, and every text field is shortened here.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

TURKU = (60.45, 22.27)  # lat, lon: the market area the forecast is for
MET = "https://api.met.no/weatherapi/metalerts/2.0/current.json?lat={lat}&lon={lon}"
GDACS = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtype=WF"
CARUNA = "https://plus.caruna.fi/current-outages.json"
WIND = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&hourly=wind_speed_10m&past_days=1&forecast_days=2&timezone=UTC"
)
USER_AGENT = "since-ai-turku-energia/1.0 (local imbalance-price forecast)"
REQUEST_TIMEOUT_S = 15
MAX_FEED_BYTES = 4_000_000
PRICE_AREAS = {"Finland", "Sweden", "Norway", "Denmark", "Estonia", "Latvia", "Lithuania"}
OUTAGE_MIN = 10  # customers without power; a single customer is noise, not a price signal
OUTAGE_HIGH = 100  # customers without power from which an outage counts as "high"
WIND_SHIFT_MS = 3.0  # m/s between the 12 h behind and the 12 h ahead
WIND_WINDOW_H = 12
WIND_MIN_HOURS = 36
DETAIL_CHARS = 240
TITLE_CHARS = 200
ID_CHARS = 100
ISO_UTC = "%Y-%m-%dT%H:%M:%SZ"
Alert = dict[str, Any]


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        parsed = json.loads(response.read(MAX_FEED_BYTES).decode(charset, "replace"))
    return parsed if isinstance(parsed, dict) else {}


def _safe(url: str) -> dict:
    """One feed; a dead or garbled feed gives {} (and a log line) so it cannot hide the others."""
    try:
        return _get(url)
    except (OSError, ValueError) as error:  # network trouble, timeouts and bad JSON
        logger.warning("alert feed unavailable (%s): %s", url.split("?")[0], error)
        return {}


def _items(container: Any, key: str) -> list[dict]:
    """The dict items of container[key]; anything else in the feed is ignored."""
    items = container.get(key) if isinstance(container, dict) else None
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _properties(feature: dict) -> dict:
    properties = feature.get("properties")
    return properties if isinstance(properties, dict) else {}


def _text(value: Any, limit: int) -> str:
    return str(value if value is not None else "")[:limit]


def _identifier(prefix: str, value: Any) -> str:
    """'met:<id>' and so on; a missing id reads 'None', as it always has."""
    return prefix + str(value)[:ID_CHARS]


def _optional_text(value: Any) -> str | None:
    return None if value is None else _text(value, ID_CHARS)


def _numbers(values: Any) -> list[float] | None:
    """`values` as a list of numbers, or None when it is no list or holds anything else (Open-Meteo sends nulls)."""
    if not isinstance(values, list):
        return None
    ok = all(isinstance(value, int | float) and not isinstance(value, bool) for value in values)
    return [float(value) for value in values] if ok else None


def _wind_shift(wind: dict) -> float | None:
    """Mean wind 12 h ahead minus 12 h behind, m/s. None when the feed is short or incomplete."""
    hourly = wind.get("hourly") if isinstance(wind, dict) else None
    hourly = hourly if isinstance(hourly, dict) else {}
    times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    if len(times) < WIND_MIN_HOURS or len(hourly.get("wind_speed_10m") or []) != len(times):
        return None
    current_hour = datetime.now(UTC).strftime("%Y-%m-%dT%H:00")
    now_index = next((index for index, stamp in enumerate(times) if str(stamp)[:16] == current_hour), None)
    if now_index is None or now_index < WIND_WINDOW_H or now_index + WIND_WINDOW_H > len(times):
        return None
    ahead = _numbers(hourly["wind_speed_10m"][now_index : now_index + WIND_WINDOW_H])
    behind = _numbers(hourly["wind_speed_10m"][now_index - WIND_WINDOW_H : now_index])
    if ahead is None or behind is None:
        return None
    return sum(ahead) / WIND_WINDOW_H - sum(behind) / WIND_WINDOW_H


def _level(text: str | None) -> str:
    """'2; yellow; Moderate' -> 'yellow'."""
    parts = str(text or "").split(";")
    return parts[1].strip().lower() if len(parts) > 1 else "yellow"


def _met_alerts(met: dict) -> list[Alert]:
    alerts = []
    for feature in _items(met, "features"):
        properties = _properties(feature)
        alerts.append(
            {
                "id": _identifier("met:", properties.get("id")),
                "kind": "weather",
                "severity": _level(properties.get("awareness_level")),
                "title": _text(
                    properties.get("title")
                    or properties.get("eventAwarenessName")
                    or properties.get("event")
                    or "weather warning",
                    TITLE_CHARS,
                ),
                "detail": _text(properties.get("description"), DETAIL_CHARS),
                "source": "MET Norway",
                "at": _optional_text(properties.get("onset")),
                "until": _optional_text(properties.get("expires") or properties.get("eventEndingTime")),
            }
        )
    return alerts


def _gdacs_alerts(gdacs: dict) -> list[Alert]:
    alerts = []
    for feature in _items(gdacs, "features"):
        properties = _properties(feature)
        if properties.get("country") not in PRICE_AREAS:
            continue
        alerts.append(
            {
                "id": _identifier("gdacs:", properties.get("eventid")),
                "kind": "disaster",
                "severity": _text(properties.get("alertlevel") or "green", ID_CHARS).lower(),
                "title": _text(properties.get("name") or properties.get("eventtype") or "disaster", TITLE_CHARS),
                "detail": _text(properties.get("description"), DETAIL_CHARS),
                "source": "GDACS",
                "at": _optional_text(properties.get("fromdate")),
                "until": _optional_text(properties.get("todate")),
            }
        )
    return alerts


def _customers(outage: dict) -> int:
    """Customers without power; a missing or odd value counts as 0."""
    size = outage.get("size")
    return int(size) if isinstance(size, int | float) and not isinstance(size, bool) else 0


def _place(outage: dict) -> str:
    """Municipality name in English, else Finnish, else '?'."""
    municipality = outage.get("municipality")
    names = municipality.get("name") if isinstance(municipality, dict) else None
    return (names.get("en") or names.get("fi") or "?") if isinstance(names, dict) else "?"


def _outage_alerts(outages: dict) -> list[Alert]:
    alerts = []
    for outage in _items(outages, "outages"):
        size = _customers(outage)
        if size < OUTAGE_MIN:
            continue
        alerts.append(
            {
                "id": _identifier("outage:", outage.get("id")),
                "kind": "outage",
                "severity": "high" if size >= OUTAGE_HIGH else "moderate",
                "title": _text(f"{outage.get('type', 'outage')} — {_place(outage)}, {size} customers", TITLE_CHARS),
                "detail": "",
                "source": "Caruna",
                "at": _optional_text(outage.get("startTime")),
                "until": _optional_text(outage.get("estimatedEndTime")),
            }
        )
    return alerts


def _wind_alerts(wind: dict) -> list[Alert]:
    shift = _wind_shift(wind)
    if shift is None or abs(shift) < WIND_SHIFT_MS:
        return []
    return [
        {
            # one stable id per direction, so a lasting shift recalculates once, not every poll
            "id": "wind:" + ("up" if shift > 0 else "down"),
            "kind": "weather",
            "severity": "high" if abs(shift) >= 2 * WIND_SHIFT_MS else "moderate",
            "title": f"Wind forecast shift {shift:+.1f} m/s over {WIND_WINDOW_H} h",
            "detail": (
                f"{WIND_WINDOW_H} h ahead vs {WIND_WINDOW_H} h behind; "
                "more wind lowers the imbalance price, less raises it."
            ),
            "source": "Open-Meteo",
            "at": datetime.now(UTC).strftime(ISO_UTC),
            "until": None,
        }
    ]


def collect(met: dict, gdacs: dict, wind: dict, outages: dict) -> list[Alert]:
    """Turn the four parsed feeds into one alert list, keeping only what can move the price."""
    return _met_alerts(met) + _gdacs_alerts(gdacs) + _outage_alerts(outages) + _wind_alerts(wind)


def fetch() -> list[Alert]:
    """Download the feeds and collect the alerts (a dead feed just contributes none)."""
    lat, lon = TURKU
    return collect(
        _safe(MET.format(lat=lat, lon=lon)),
        _safe(GDACS),
        _safe(WIND.format(lat=lat, lon=lon)),
        _safe(CARUNA),
    )
