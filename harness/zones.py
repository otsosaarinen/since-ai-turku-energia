"""
zones.py — installed wind/solar capacity per Nord Pool bidding zone, and the
capacity density (MW per 100 km2) plus the keyless weather and spot series
needed to correlate weather with the plant base.

area_km2 and the centroid are computed from Electricity Maps bidding-zone
geometry (geo/world.geojson, zoneName field), not from administrative borders —
the price-area borders follow the transmission grid, so county areas would be wrong.

Capacity is the last published figure per zone. Rebuild the table when a zone's
capacity moves materially; the numbers are dated in `source`.
"""

import json

try:
    from . import sources  # imported as harness.zones
except ImportError:  # run from inside harness/
    import sources

# zone: (name, area_km2, lat, lon, wind_MW, solar_MW, source)
ZONES = {
    "SE1": ("Luleå/N Norrland", 117183.5, 66.750, 20.086, 3144, 50,
            "Energiföretagen Energiåret 2025, installed capacity per elområde"),
    "SE2": ("Sundsvall/Norrland", 141121.8, 63.597, 15.999, 7957, 261,
            "Energiföretagen Energiåret 2025"),
    "SE3": ("Stockholm", 149437.2, 59.336, 14.743, 4555, 2578,
            "Energiföretagen Energiåret 2025"),
    "SE4": ("Malmö/S Sweden", 38825.5, 56.574, 14.394, 2687, 2652,
            "Energiföretagen Energiåret 2025"),
    "NO1": ("Oslo/E Norway", 60332.5, 60.903, 10.706, 384.7, 300,
            "wind: NVE Vindkraftdatabase (plants in operation, live API); solar: NVE national, split estimate"),
    "NO2": ("Kristiansand/SW Norway", 47642.8, 59.193, 7.652, 1427.0, 130,
            "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate"),
    "NO3": ("Trondheim/M Norway", 65400.3, 62.777, 9.141, 2107.8, 90,
            "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate"),
    "NO4": ("Tromsø/N Norway", 116882.3, 68.570, 20.571, 1159.2, 60,
            "wind: NVE Vindkraftdatabase; solar: NVE national, split estimate"),
    "NO5": ("Bergen/W Norway", 24831.0, 60.761, 7.209, 0.0, 120,
            "wind: NVE Vindkraftdatabase (no plant assigned to NO5); solar: split estimate"),
    "FI":  ("Finland", 330038.9, 64.506, 26.283, 9535, 1300,
            "wind: Renewables Finland H1 2026 via pv magazine; solar: utility-scale 842 MW + rooftop estimate"),
    "DK1": ("Jutland/Funen", 31994.9, 56.153, 9.471, 4900, 2730,
            "Energinet/Forsyningstilsynet national 2024-26 split, estimate"),
    "DK2": ("Zealand", 9766.1, 55.386, 12.016, 2160, 1170,
            "Energinet/Forsyningstilsynet national 2024-26 split, estimate"),
}


def table():
    """One row per zone: capacity, area, density per 100 km2."""
    rows = []
    for zone, (name, area, lat, lon, wind, solar, src) in ZONES.items():
        rows.append({
            "zone": zone, "name": name, "lat": lat, "lon": lon,
            "area_km2": round(area), "wind_mw": wind, "solar_mw": solar,
            "wind_mw_per_100km2": round(wind / (area / 100.0), 2),
            "solar_mw_per_100km2": round(solar / (area / 100.0), 2),
            "source": src,
        })
    return rows


def weather(zone, days=3):
    """Hourly cloud cover %, GHI W/m2 and wind at 100 m for the zone centroid.

    One open-meteo call; keyless. Uses the repo's sun_position feed, which already
    carries shortwave_radiation + cloud_cover; wind 100 m is appended here because
    turbines sit at hub height, not 10 m.
    """
    _, _, lat, lon, _, _, _ = ZONES[zone]
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&hourly=cloud_cover,shortwave_radiation,wind_speed_100m"
           f"&forecast_days={days}&wind_speed_unit=ms&timezone=UTC")
    return _json(url)


def spot(zone, date):
    """Day-ahead spot EUR/MWh for the zone on a date (Nord Pool dataportal, keyless)."""
    url = ("https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
           f"?date={date}&market=DayAhead&deliveryArea={zone}&currency=EUR")
    data = _json(url)
    return [(e["deliveryStart"], e["entryPerArea"].get(zone)) for e in data["multiAreaEntries"]]


def _json(url):
    """fetch_url returns pretty JSON text or an 'Error: ...' line; both are surfaced as-is."""
    body = sources.fetch_url(url)
    try:
        return json.loads(body)
    except ValueError as e:
        raise RuntimeError(f"fetch failed for {url}: {body[:200]}") from e


def _pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x, _ in pairs)
    syy = sum((y - my) ** 2 for _, y in pairs)
    if sxx == 0 or syy == 0:
        return None
    return round(sxy / (sxx * syy) ** 0.5, 3)


def _hourly_price(zone, date, hours):
    """Spot averaged to the weather's hourly grid; None where the hour has no price."""
    hourly = {}
    for stamp, price in spot(zone, date):
        if price is None:
            continue
        hourly.setdefault(stamp[:13], []).append(price)
    return [round(sum(hourly[h[:13]]) / len(hourly[h[:13]]), 2) if hourly.get(h[:13]) else None
            for h in hours]


def correlate(zone, date, days=1):
    """r(cloud, spot) and r(wind_100m, spot) for a zone, hourly.

    The correlation is weather against the zone's own price, so a zone with a large
    plant base and few interconnectors shows the strongest signal. Price is 15 min;
    it is averaged to the hour to match the weather series.
    """
    w = weather(zone, days)["hourly"]
    prices = _hourly_price(zone, date, w["time"])
    return {
        "zone": zone,
        "hours": len(w["time"]),
        "priced_hours": sum(1 for p in prices if p is not None),
        "r_cloud_spot": _pearson(w["cloud_cover"], prices),
        "r_wind_spot": _pearson(w["wind_speed_100m"], prices),
    }


def _wind_fraction(v):
    """Standard turbine curve: cut-in 3 m/s, linear to rated at 12, cut-out 25."""
    if v is None or v < 3 or v > 25:
        return 0.0
    return 1.0 if v >= 12 else (v - 3) / 9.0


def _slope(xs, ys):
    """OLS dEuros/MWh per MW — the fitted price response to one more MW of output."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    mx = sum(p[0] for p in pairs) / len(pairs)
    my = sum(p[1] for p in pairs) / len(pairs)
    sxx = sum((x - mx) ** 2 for x, _ in pairs)
    if sxx == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in pairs) / sxx, 4)


def cf(zone, date, days=1):
    """Modelled hourly wind and solar output (MW) for a zone, and how it moves price.

    Production = capacity * capacity factor from the zone's own weather: wind from the
    turbine curve at 100 m, solar from GHI/1000. The MW are modelled (capacity is
    installed nameplate), so they are an output estimate, not metered generation.
    The slopes are the price response — EUR/MWh per MW of extra output — fitted on the
    day's hours; they are the "production affects EUR/MWh" link, not a causal estimate.
    """
    _, _, _, _, wind_mw, solar_mw, _ = ZONES[zone]
    w = weather(zone, days)["hourly"]
    prices = _hourly_price(zone, date, w["time"])
    wind = [round(_wind_fraction(v) * wind_mw, 1) for v in w["wind_speed_100m"]]
    solar = [round((g or 0) / 1000 * solar_mw, 1) for g in w["shortwave_radiation"]]
    return {
        "zone": zone,
        "capacity_mw": {"wind": wind_mw, "solar": solar_mw},
        "priced_hours": sum(1 for p in prices if p is not None),
        "mean_wind_mw": round(sum(wind) / len(wind), 1),
        "mean_solar_mw": round(sum(solar) / len(solar), 1),
        "peak_wind_mw": max(wind),
        "peak_solar_mw": max(solar),
        "r_wind_prod_spot": _pearson(wind, prices),
        "r_solar_prod_spot": _pearson(solar, prices),
        "eur_per_mwh_per_wind_mw": _slope(wind, prices),
        "eur_per_mwh_per_solar_mw": _slope(solar, prices),
    }
