"""Live alerts that can move the Finnish imbalance price.

Three keyless feeds — MET Norway weather warnings, GDACS disasters and Caruna network outages —
plus the wind forecast, parsed into one short list. `collect` is pure (takes the parsed JSON);
`fetch` is the network layer. The harness server polls this and reruns the forecast on a new id.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone

TURKU = (60.45, 22.27)  # lat, lon: the market area the forecast is for
MET = "https://api.met.no/weatherapi/metalerts/2.0/current.json?lat={lat}&lon={lon}"
GDACS = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtype=WF"
CARUNA = "https://plus.caruna.fi/current-outages.json"
WIND = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m&past_days=1&forecast_days=2&timezone=UTC")
UA = "since-ai-turku-energia/1.0 (local imbalance-price forecast)"
PRICE_AREAS = {"Finland", "Sweden", "Norway", "Denmark", "Estonia", "Latvia", "Lithuania"}
OUTAGE_MIN = 10      # customers without power; a single customer is noise, not a price signal
WIND_SHIFT_MS = 3.0  # m/s between the 12 h behind and the 12 h ahead


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read(4_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace"))


def _safe(url: str) -> dict:
    try:
        return _get(url)
    except Exception:
        return {}  # one dead feed must not hide the others


def _wind_shift(wind: dict) -> float | None:
    """Mean wind 12 h ahead minus 12 h behind, m/s. None when the feed is short."""
    h = (wind or {}).get("hourly") or {}
    times, vals = h.get("time") or [], h.get("wind_speed_10m") or []
    if len(times) < 36 or len(vals) != len(times):
        return None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    i = next((k for k, t in enumerate(times) if t[:16] == now), None)
    if i is None or i < 12 or i + 12 > len(vals):
        return None
    return sum(vals[i:i + 12]) / 12 - sum(vals[i - 12:i]) / 12


def _level(text: str | None) -> str:
    """'2; yellow; Moderate' -> 'yellow'."""
    parts = str(text or "").split(";")
    return parts[1].strip().lower() if len(parts) > 1 else "yellow"


def collect(met: dict, gdacs: dict, wind: dict, outages: dict) -> list[dict]:
    out = []
    for f in (met or {}).get("features") or []:
        p = f.get("properties") or {}
        out.append({
            "id": "met:" + str(p.get("id")), "kind": "weather", "severity": _level(p.get("awareness_level")),
            "title": p.get("title") or p.get("eventAwarenessName") or p.get("event") or "weather warning",
            "detail": str(p.get("description") or "")[:240], "source": "MET Norway",
            "at": p.get("onset"), "until": p.get("expires") or p.get("eventEndingTime"),
        })
    for f in (gdacs or {}).get("features") or []:
        p = f.get("properties") or {}
        if p.get("country") not in PRICE_AREAS:
            continue
        out.append({
            "id": "gdacs:" + str(p.get("eventid")), "kind": "disaster", "severity": str(p.get("alertlevel") or "green").lower(),
            "title": p.get("name") or p.get("eventtype") or "disaster", "detail": str(p.get("description") or "")[:240],
            "source": "GDACS", "at": p.get("fromdate"), "until": p.get("todate"),
        })
    for o in (outages or {}).get("outages") or []:
        size = o.get("size") or 0
        if size < OUTAGE_MIN:
            continue
        m = (o.get("municipality") or {}).get("name") or {}
        out.append({
            "id": "outage:" + str(o.get("id")), "kind": "outage", "severity": "high" if size >= 100 else "moderate",
            "title": f"{o.get('type', 'outage')} — {m.get('en') or m.get('fi') or '?'}, {size} customers",
            "detail": "", "source": "Caruna", "at": o.get("startTime"), "until": o.get("estimatedEndTime"),
        })
    shift = _wind_shift(wind)
    if shift is not None and abs(shift) >= WIND_SHIFT_MS:
        out.append({
            # one stable id per direction, so a lasting shift recalculates once, not every poll
            "id": "wind:" + ("up" if shift > 0 else "down"), "kind": "weather",
            "severity": "high" if abs(shift) >= 2 * WIND_SHIFT_MS else "moderate",
            "title": f"Wind forecast shift {shift:+.1f} m/s over 12 h",
            "detail": "12 h ahead vs 12 h behind; more wind lowers the imbalance price, less raises it.",
            "source": "Open-Meteo", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "until": None,
        })
    return out


def fetch() -> list[dict]:
    lat, lon = TURKU
    return collect(
        _safe(MET.format(lat=lat, lon=lon)),
        _safe(GDACS),
        _safe(WIND.format(lat=lat, lon=lon)),
        _safe(CARUNA),
    )
