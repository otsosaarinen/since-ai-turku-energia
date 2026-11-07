"""Installed wind/solar capacity per Nord Pool bidding zone, plus weather and spot series to relate them to price.

The model reaches this from `run_python` as `from harness import zones`
(`zones.cf(zone, date)`, `zones.correlate(zone, date)`).
Area and centroid come from Electricity Maps bidding-zone geometry (geo/world.geojson, zoneName), not administrative
borders: price-area borders follow the transmission grid. Capacity is the last published figure per zone; the numbers
are dated in `source`, and the table should be rebuilt when a zone's capacity moves materially.
"""

import json
import re
from typing import Any, NamedTuple
from urllib.parse import quote

from . import sources
from .sources import QUOTE_SAFE

CUT_IN_MS = 3.0  # standard turbine curve: nothing below cut-in, linear to rated, nothing above cut-out
RATED_MS = 12.0
CUT_OUT_MS = 25.0
AREA_CODE = re.compile(r"^[A-Z0-9]{2,4}$")
MIN_PAIRS = 3  # fewer points than this give no correlation or slope


class Zone(NamedTuple):
    name: str
    area_km2: float
    lat: float
    lon: float
    wind_mw: float
    solar_mw: float
    source: str


ZONES: dict[str, Zone] = {
    "SE1": Zone(
        "Luleå/N Norrland",
        117183.5,
        66.750,
        20.086,
        3144,
        50,
        "Energiföretagen Energiåret 2025, installed capacity per elområde",
    ),
    "SE2": Zone("Sundsvall/Norrland", 141121.8, 63.597, 15.999, 7957, 261, "Energiföretagen Energiåret 2025"),
    "SE3": Zone("Stockholm", 149437.2, 59.336, 14.743, 4555, 2578, "Energiföretagen Energiåret 2025"),
    "SE4": Zone("Malmö/S Sweden", 38825.5, 56.574, 14.394, 2687, 2652, "Energiföretagen Energiåret 2025"),
    "NO1": Zone(
        "Oslo/E Norway",
        60332.5,
        60.903,
        10.706,
        384.7,
        300,
        "wind: NVE Vindkraftdatabase (plants in operation, live API); solar: NVE national, split estimate",
    ),
    "NO2": Zone(
        "Kristiansand/SW Norway",
        47642.8,
        59.193,
        7.652,
        1427.0,
        130,
        "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate",
    ),
    "NO3": Zone(
        "Trondheim/M Norway",
        65400.3,
        62.777,
        9.141,
        2107.8,
        90,
        "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate",
    ),
    "NO4": Zone(
        "Tromsø/N Norway",
        116882.3,
        68.570,
        20.571,
        1159.2,
        60,
        "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate",
    ),
    "NO5": Zone(
        "Bergen/W Norway",
        24831.0,
        60.761,
        7.209,
        0.0,
        120,
        "wind: NVE Vindkraftdatabase (no plant assigned to NO5); solar: split estimate",
    ),
    "FI": Zone(
        "Finland",
        330038.9,
        64.506,
        26.283,
        9535,
        1300,
        "wind: Renewables Finland H1 2026 via pv magazine; solar: utility-scale 842 MW + rooftop estimate",
    ),
    "DK1": Zone(
        "Jutland/Funen",
        31994.9,
        56.153,
        9.471,
        4900,
        2730,
        "Energinet/Forsyningstilsynet national 2024-26 split, estimate",
    ),
    "DK2": Zone(
        "Zealand", 9766.1, 55.386, 12.016, 2160, 1170, "Energinet/Forsyningstilsynet national 2024-26 split, estimate"
    ),
}


def table() -> list[dict[str, Any]]:
    """One row per zone: capacity, area and density per 100 km2."""
    rows = []
    for code, zone in ZONES.items():
        per_100km2 = zone.area_km2 / 100.0
        rows.append(
            {
                "zone": code,
                "name": zone.name,
                "lat": zone.lat,
                "lon": zone.lon,
                "area_km2": round(zone.area_km2),
                "wind_mw": zone.wind_mw,
                "solar_mw": zone.solar_mw,
                "wind_mw_per_100km2": round(zone.wind_mw / per_100km2, 2),
                "solar_mw_per_100km2": round(zone.solar_mw / per_100km2, 2),
                "source": zone.source,
            }
        )
    return rows


def _json(url: str) -> Any:
    """fetch_url returns pretty JSON text or an 'Error: ...' line; an error line becomes an exception."""
    body = sources.fetch_url(url)
    try:
        return json.loads(body)
    except ValueError as error:
        raise RuntimeError(f"fetch failed for {url}: {body[:200]}") from error


def weather(zone: str, days: int = 3) -> dict[str, Any]:
    """Hourly cloud cover %, GHI W/m2 and wind at 100 m for the zone centroid (one keyless open-meteo call).

    Wind is taken at 100 m because turbines sit at hub height, not 10 m.
    """
    place = ZONES[zone]
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={place.lat}&longitude={place.lon}"
        "&hourly=cloud_cover,shortwave_radiation,wind_speed_100m"
        f"&forecast_days={int(days)}&wind_speed_unit=ms&timezone=UTC"
    )
    return _json(url)


def spot(zone: str, date: str) -> list[tuple[str, float | None]]:
    """Day-ahead spot EUR/MWh for the zone on a date (Nord Pool dataportal, keyless): (delivery start, price) pairs."""
    if not AREA_CODE.match(zone):  # the zone goes into a URL: only a bidding-zone code is acceptable
        raise ValueError(f"not a bidding-zone code: {zone!r}")
    safe_date = quote(str(date), safe=QUOTE_SAFE)
    url = (
        "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
        f"?date={safe_date}&market=DayAhead&deliveryArea={zone}&currency=EUR"
    )
    entries = _json(url)["multiAreaEntries"]
    return [(entry["deliveryStart"], entry["entryPerArea"].get(zone)) for entry in entries]


def _valid_pairs(xs: list[float | None], ys: list[float | None]) -> list[tuple[float, float]]:
    return [(x, y) for x, y in zip(xs, ys, strict=False) if x is not None and y is not None]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _pearson(xs: list[float | None], ys: list[float | None]) -> float | None:
    """Correlation of the points where both values exist; None with too few points or no variation."""
    pairs = _valid_pairs(xs, ys)
    if len(pairs) < MIN_PAIRS:
        return None
    mean_x, mean_y = _mean([x for x, _ in pairs]), _mean([y for _, y in pairs])
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    variance_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    variance_y = sum((y - mean_y) ** 2 for _, y in pairs)
    if variance_x == 0 or variance_y == 0:
        return None
    return round(covariance / (variance_x * variance_y) ** 0.5, 3)


def _slope(xs: list[float | None], ys: list[float | None]) -> float | None:
    """Least-squares EUR/MWh per MW: the fitted price response to one more MW of output."""
    pairs = _valid_pairs(xs, ys)
    if len(pairs) < MIN_PAIRS:
        return None
    mean_x, mean_y = _mean([x for x, _ in pairs]), _mean([y for _, y in pairs])
    variance_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    if variance_x == 0:
        return None
    return round(sum((x - mean_x) * (y - mean_y) for x, y in pairs) / variance_x, 4)


def _hourly_price(zone: str, date: str, hours: list[str]) -> list[float | None]:
    """Spot averaged to the weather's hourly grid; None where an hour has no price."""
    by_hour: dict[str, list[float]] = {}
    for stamp, price in spot(zone, date):
        if price is not None:
            by_hour.setdefault(stamp[:13], []).append(price)
    return [round(_mean(by_hour[hour[:13]]), 2) if by_hour.get(hour[:13]) else None for hour in hours]


def correlate(zone: str, date: str, days: int = 1) -> dict[str, Any]:
    """r(cloud, spot) and r(wind_100m, spot) for a zone, hourly (15 min prices are averaged to the hour).

    A zone with a large plant base and few interconnectors shows the strongest weather-to-price signal.
    """
    hourly = weather(zone, days)["hourly"]
    prices = _hourly_price(zone, date, hourly["time"])
    return {
        "zone": zone,
        "hours": len(hourly["time"]),
        "priced_hours": sum(1 for price in prices if price is not None),
        "r_cloud_spot": _pearson(hourly["cloud_cover"], prices),
        "r_wind_spot": _pearson(hourly["wind_speed_100m"], prices),
    }


def _wind_fraction(speed_ms: float | None) -> float:
    """Share of rated wind output at a wind speed (0 below cut-in or above cut-out, 1 from rated speed up)."""
    if speed_ms is None or speed_ms < CUT_IN_MS or speed_ms > CUT_OUT_MS:
        return 0.0
    return 1.0 if speed_ms >= RATED_MS else (speed_ms - CUT_IN_MS) / (RATED_MS - CUT_IN_MS)


def cf(zone: str, date: str, days: int = 1) -> dict[str, Any]:
    """Modelled hourly wind and solar output (MW) for a zone, and how it moves price.

    Production = nameplate capacity x capacity factor from the zone's own weather: wind from the turbine curve at 100 m,
    solar from GHI/1000. The MW are modelled, an output estimate and not metered generation. The slopes are the price
    response (EUR/MWh per MW of extra output) fitted on the day's hours: an association, not a causal estimate.
    """
    capacity = ZONES[zone]
    hourly = weather(zone, days)["hourly"]
    prices = _hourly_price(zone, date, hourly["time"])
    wind = [round(_wind_fraction(speed) * capacity.wind_mw, 1) for speed in hourly["wind_speed_100m"]]
    solar = [round((radiation or 0) / 1000 * capacity.solar_mw, 1) for radiation in hourly["shortwave_radiation"]]
    return {
        "zone": zone,
        "capacity_mw": {"wind": capacity.wind_mw, "solar": capacity.solar_mw},
        "priced_hours": sum(1 for price in prices if price is not None),
        "mean_wind_mw": round(_mean(wind), 1),
        "mean_solar_mw": round(_mean(solar), 1),
        "peak_wind_mw": max(wind),
        "peak_solar_mw": max(solar),
        "r_wind_prod_spot": _pearson(wind, prices),
        "r_solar_prod_spot": _pearson(solar, prices),
        "eur_per_mwh_per_wind_mw": _slope(wind, prices),
        "eur_per_mwh_per_solar_mw": _slope(solar, prices),
    }
