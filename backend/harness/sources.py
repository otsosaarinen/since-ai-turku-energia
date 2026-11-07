"""Named live data sources and the two fetch tools (`get_data`, `fetch_url`) the model may call.

Only the hosts of the sources below can be fetched, over https; a redirect to any other host is refused, so a page
cannot bounce a request (or its API key) somewhere else. Keys are read from the environment at call time and are
never put in anything the model sees.
"""

import http.client
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlsplit

from .safety import redact

logger = logging.getLogger(__name__)

MAX_BYTES = 1_000_000  # largest response body read
MAX_CHARS = 20_000  # largest text handed back to the model
REQUEST_TIMEOUT_S = 15
MAX_ATTEMPTS = 5  # Fingrid allows about 1 request a second, so a 429 is retried
RETRY_STATUS = (429, 403, 502, 503, 504)  # transient: Fingrid 429, one outage CDN edge answers 403 at random
RETRY_PAUSE_S = 1.5
USER_AGENT = "livelectroray-harness/1"
KEY_HEADERS = ("x-api-key",)  # never forwarded to another host on a redirect
DEFAULT_LOOKBACK_HOURS = 2
ISO_UTC = "%Y-%m-%dT%H:%M:%SZ"
QUOTE_SAFE = "-:._~"  # parameter values are percent-encoded, so one cannot add query fields or break the URL
THIN_MIN_ROWS = 8


def _fingrid(dataset: int, *, back: int = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any]:
    """A Fingrid open-data series (needs FINGRID_API_KEY); the window defaults to the last `back` hours."""
    source: dict[str, Any] = {
        "url": f"https://data.fingrid.fi/api/datasets/{dataset}/data?startTime={{start}}&endTime={{end}}&pageSize=20",
        "params": f"start, end = ISO8601 (default: last {back} hours)",
        "key": "FINGRID_API_KEY",
        "headers": {"x-api-key": "FINGRID_API_KEY"},
    }
    if back != DEFAULT_LOOKBACK_HOURS:
        source["back"] = back  # laggy series look further back
    return source


# Named sources the model may pull from. {placeholders} are filled by get_data(); hosts outside this set are refused.
SOURCES: dict[str, dict[str, Any]] = {
    "nordpool_price": {  # day-ahead spot price, every area, keyless
        "url": "https://dashboard.elering.ee/api/nps/price?start={start}&end={end}",
        "params": "start,end = ISO8601 UTC (optional; default: 1 hour ago to 48 hours ahead, every published hour)",
        "back": 1,  # hours before now when no start is given
        "ahead": 48,  # hours after now when no end is given
        "note": "same Nord Pool spot for all areas; Fingrid sells no price in open data",
    },
    "spot_price_fi": {  # Finland current spot, keyless
        "url": "https://api.spot-hinta.fi/JustNow",
        "params": "",
    },
    "nordpool_dayahead": {  # Nord Pool day-ahead per bidding zone, 15 min EUR/MWh, keyless
        "url": "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
        "?date={date}&market=DayAhead&deliveryArea={area}&currency=EUR",
        "params": "date = YYYY-MM-DD, area = SE1|SE2|SE3|SE4|NO1..NO5|DK1|DK2|FI",
        "note": "elering (nordpool_price) only carries EE/LV/LT/FI; this carries every zone",
    },
    # Statnett (Norway's TSO) open REST, keyless — Nordic-wide, not just NO.
    "statnett_overview": {  # latest Nordic production/consumption per area by source, MW
        "url": "https://driftsdata.statnett.no/restapi/ProductionConsumption/GetLatestDetailedOverview",
        "params": "",
        "note": "one call covers NO1-5 + SE + FI + DK by hydro/wind/nuclear/thermal + net exchange",
    },
    "statnett_prodcons": {  # Nordic production/consumption daily series, MW
        "url": "https://driftsdata.statnett.no/restapi/ProductionConsumption/GetData",
        "params": "From,To = YYYY-MM-DD (optional, default last 7 days; append via fetch_url)",
    },
    "statnett_flow": {  # Nordic net physical exchange daily series, MW
        "url": "https://driftsdata.statnett.no/restapi/PhysicalFlow/GetData",
        "params": "From = YYYY-MM-DD (optional, default last 7 days; append via fetch_url)",
    },
    "statnett_power_situation": {  # Statnett's grid-capacity assessment per NO price area
        "url": "https://driftsdata.statnett.no/restapi/ElspotPowerSituation/GetPowerSituations",
        "params": "",
    },
    "statnett_reservoir": {  # Norwegian hydro reservoir fill % per NO area + total, weekly
        "url": "https://driftsdata.statnett.no/restapi/Reservoir/LastWeekData/{weeks}",
        "params": "weeks (optional, default 3; up to 52)",
        "defaults": {"weeks": 3},
        "note": "the multi-week hydro/price driver for the Norwegian zones",
    },
    "cloud_wind": {  # ICOWL weather+wind source (open-meteo): cloud cover, wind
        "url": "https://api.open-meteo.com/v1/forecast"
        "?latitude={lat}&longitude={lon}"
        "&current=cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,temperature_2m"
        "&hourly=cloud_cover,wind_speed_10m,wind_gusts_10m,temperature_2m"
        "&forecast_days=8&wind_speed_unit=ms&timezone=UTC",
        "params": "lat, lon (required)",
        "note": "current + hourly out to 8 days, the forward weather for wind prediction",
    },
    "sun_position": {  # solar irradiance + daylight window, for solar productivity (open-meteo)
        "url": "https://api.open-meteo.com/v1/forecast"
        "?latitude={lat}&longitude={lon}"
        "&current=shortwave_radiation,direct_normal_irradiance,diffuse_radiation,terrestrial_radiation"
        "&hourly=shortwave_radiation,direct_normal_irradiance,cloud_cover"
        "&daily=sunrise,sunset,daylight_duration,sunshine_duration"
        "&forecast_days=8&timezone=UTC",
        "params": "lat, lon (required)",
        "note": "W/m2 GHI/DNI + sunrise/sunset, current and hourly to 8 days; "
        "max potential PV ~ GHI * panel area * efficiency",
    },
    "warnings_areal": {  # areal disaster warnings, Nordics (MET Norway)
        "url": "https://api.met.no/weatherapi/metalerts/2.0/current.json?lat={lat}&lon={lon}",
        "params": "lat, lon (required)",
    },
    "warnings_global": {  # ICOWL hazard feed (GDACS)
        "url": "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtype={eventtype}",
        "params": "eventtype (optional)",
        "defaults": {"eventtype": "WF"},
    },
    "outages_caruna": {  # Caruna DSO live network outages, keyless
        "url": "https://plus.caruna.fi/current-outages.json",
        "params": "",
    },
    "outages_finland_dso": {  # every Finnish DSO live outage summary, keyless
        "url": "https://sqtb-api.azureedge.net/outagemap/tailored/summary/",
        "params": "",
        "hdr": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Origin": "https://sahkotutka.fi",
            "Referer": "https://sahkotutka.fi/",
        },
        "note": "serves 403 without an Origin header",
    },
    "transfer_capacity": {  # regional transfer capacity, day-ahead (ENTSO-E docType A61)
        "url": "https://web-api.tp.entsoe.eu/api?securityToken={token}"
        "&documentType=A61&contract_MarketAgreement.Type=A01"
        "&in_Domain={in_domain}&out_Domain={out_domain}"
        "&periodStart={start}&periodEnd={end}",
        "params": "in_domain, out_domain = EIC codes (FI 10YFI-1--------U), start, end = YYYYMMDDHHMM (required)",
        "key": "ENTSOE_API_KEY",
    },
    "transfer_flow": {  # live amount crossing a border (ENTSO-E docType A11)
        "url": "https://web-api.tp.entsoe.eu/api?securityToken={token}"
        "&documentType=A11&in_Domain={in_domain}&out_Domain={out_domain}"
        "&periodStart={start}&periodEnd={end}",
        "params": "in_domain, out_domain = EIC codes, start, end = YYYYMMDDHHMM (required)",
        "key": "ENTSOE_API_KEY",
    },
    "fingrid_flow": _fingrid(87),  # FI-SE1 tie line, real-time MW (positive = export)
    "fingrid_net_import": _fingrid(194),  # Finland net import/export, real-time MW
    "fingrid_frequency": _fingrid(177),  # system frequency, real-time Hz
    "fingrid_consumption": _fingrid(193),  # Finland consumption, real-time MW
    "fingrid_solar_capacity": _fingrid(
        267, back=6
    ),  # installed solar capacity behind the forecast, MW (hourly, lagged)
    "fingrid_wind_gen": _fingrid(181),  # Finland wind production, real-time MW (3 min)
    "fingrid_imbalance_price": _fingrid(319),  # imbalance price, 15 min, EUR/MWh: the near-term price driver
    "fingrid_nuclear": _fingrid(188),  # Finland nuclear production, real-time MW (OL3 is ~1600 MW)
    "fingrid_hydro": _fingrid(191),  # Finland hydro production, real-time MW
    "fingrid_production": _fingrid(192),  # total Finland production, real-time MW
    "fingrid_surplus": _fingrid(198),  # Finland production surplus/deficit, real-time MW (negative = deficit)
    "fingrid_imbalance_power": _fingrid(176),  # imbalance power FI-SE, hourly MW
    "capacity_fi_se1": _fingrid(44),  # intraday transfer capacity FI-SE1, 15 min MW
    "capacity_fi_ee": _fingrid(111),  # intraday transfer capacity FI-EE, 15 min MW
}
ALLOWED_HOSTS = {urlsplit(source["url"]).hostname for source in SOURCES.values()}


class _ScopedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to https on an allowed host, and never hand key headers to a different host."""

    def redirect_request(
        self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> urllib.request.Request | None:
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in ALLOWED_HOSTS:
            raise urllib.error.HTTPError(req.full_url, code, f"redirect to {target.hostname} refused", headers, fp)
        follow = super().redirect_request(req, fp, code, msg, headers, newurl)
        if follow is not None and target.hostname != urlsplit(req.full_url).hostname:
            for header in list(follow.headers):
                if header.lower() in KEY_HEADERS:
                    del follow.headers[header]
        return follow


_OPENER = urllib.request.build_opener(_ScopedRedirects)


def iso_utc(moment: datetime) -> str:
    """ISO8601 UTC text such as 2026-11-07T12:30:00Z."""
    return moment.astimezone(UTC).strftime(ISO_UTC)


def _read_body(url: str, headers: dict[str, str] | None) -> str:
    """GET with retries on transient statuses; raises the last error."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with _OPENER.open(request, timeout=REQUEST_TIMEOUT_S) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(MAX_BYTES).decode(charset, "replace")
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(RETRY_PAUSE_S * attempt)
    raise AssertionError("unreachable")  # the loop either returns or raises


def _longest_list(root: Any) -> tuple[Any, Any] | None:
    """(container, key) of the longest list longer than THIN_MIN_ROWS anywhere inside `root`, or None."""
    best: tuple[int, Any, Any] | None = None
    pending = [root]
    while pending:
        node = pending.pop()
        children = node.items() if isinstance(node, dict) else enumerate(node)
        for key, value in children:
            if isinstance(value, list):
                if len(value) > THIN_MIN_ROWS and (best is None or len(value) > best[0]):
                    best = (len(value), node, key)
                pending.append(value)
            elif isinstance(value, dict):
                pending.append(value)
    return None if best is None else (best[1], best[2])


def _thin(rows: list[Any]) -> list[Any]:
    """Every second row, always keeping the last one so the time span stays the same."""
    kept = rows[::2]
    if kept[-1] is not rows[-1]:
        kept.append(rows[-1])
    return kept


def _shorten(body: str) -> str:
    """JSON is pretty-printed and kept valid: the longest list anywhere in it is thinned until the text fits MAX_CHARS.

    (The Elering price feed nests its lists as data.fi, data.ee, ...; cutting the text instead of thinning produced a
    file that stopped mid-record, which Python could not load.) Only non-JSON bodies, or JSON with no long list,
    are cut.
    """
    try:
        parsed = json.loads(body)
    except ValueError:
        return body[:MAX_CHARS]
    holder = {"value": parsed}  # lets a top-level list be replaced like any other
    text = json.dumps(parsed, indent=2)
    while len(text) > MAX_CHARS:
        longest = _longest_list(holder)
        if longest is None:
            break
        container, key = longest
        container[key] = _thin(container[key])
        text = json.dumps(holder["value"], indent=2)
    return text[:MAX_CHARS]


def fetch_url(url: str, headers: dict[str, str] | None = None) -> str:
    """GET a URL on an allowed host over https and return the body (JSON pretty-printed); failures are 'Error: ...'."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        allowed = ", ".join(sorted(host for host in ALLOWED_HOSTS if host))
        return f"Error: {parts.hostname} is out of the Nord Pool scope or not https; allowed hosts: {allowed}"
    try:
        return _shorten(_read_body(url, headers))
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
        logger.debug("fetch failed for host %s: %s", parts.hostname, type(error).__name__)
        return redact(f"Error: {error}")  # an invalid-URL error can quote the URL, which may hold the ENTSO-E token


def _with_default_window(spec: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Fill a missing start/end of a windowed source: the last few hours up to now, or up to `ahead` hours later."""
    now = datetime.now(UTC)
    window = {
        "start": iso_utc(now - timedelta(hours=spec.get("back", DEFAULT_LOOKBACK_HOURS))),
        "end": iso_utc(now + timedelta(hours=spec.get("ahead", 0))),
    }
    return {**{name: text for name, text in window.items() if "{" + name + "}" in spec["url"]}, **values}


def get_data(source: str, params: dict[str, Any] | None = None) -> str:
    """Fetch a named source (see SOURCES), filling its {placeholders} with percent-encoded `params`."""
    spec = SOURCES.get(source)
    if not spec:
        return f"Error: unknown source {source!r}; use one of: {', '.join(SOURCES)}"
    key_name = spec.get("key")
    if key_name and not os.environ.get(key_name):
        return f"Error: source {source!r} needs {key_name} in the environment"
    values = {**spec.get("defaults", {}), **(params or {})}
    values = _with_default_window(spec, values)
    encoded = {name: quote(str(value), safe=QUOTE_SAFE) for name, value in values.items()}
    encoded["token"] = os.environ.get("ENTSOE_API_KEY", "")  # always ours: the model cannot supply or override it
    headers = {
        **spec.get("hdr", {}),
        **{header: os.environ.get(env, "") for header, env in spec.get("headers", {}).items()},
    }
    try:
        url = spec["url"].format(**encoded)
    except KeyError as missing:
        return f"Error: source {source!r} needs parameter {missing} ({spec['params']})"
    return fetch_url(url, headers=headers)
