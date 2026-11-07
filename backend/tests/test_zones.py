"""Guards the baked zone table and the correlation maths; no network."""

from harness import zones


def test_table_covers_every_nord_pool_zone():
    rows = zones.table()
    assert len(rows) == 12
    assert {r["zone"] for r in rows} == {
        "SE1",
        "SE2",
        "SE3",
        "SE4",
        "NO1",
        "NO2",
        "NO3",
        "NO4",
        "NO5",
        "FI",
        "DK1",
        "DK2",
    }
    for r in rows:
        assert r["area_km2"] > 0 and r["source"]
        assert r["wind_mw_per_100km2"] >= 0 and r["solar_mw_per_100km2"] >= 0


def test_density_matches_capacity_and_area():
    for r in zones.table():
        expect = r["wind_mw"] / (r["area_km2"] / 100.0)
        assert abs(r["wind_mw_per_100km2"] - expect) < 0.02


def test_wind_curve_and_slope():
    assert zones._wind_fraction(2) == 0.0
    assert zones._wind_fraction(3) == 0.0
    assert zones._wind_fraction(7.5) == 0.5
    assert zones._wind_fraction(12) == 1.0
    assert zones._wind_fraction(26) == 0.0
    assert zones._slope([1, 2, 3], [2, 4, 6]) == 2.0
    assert zones._slope([1, 1, 1], [2, 3, 4]) is None


def test_cf_scales_capacity_with_weather(monkeypatch):
    """Rated wind at 12 m/s returns the zone's full wind MW; no sun means no solar MW."""
    monkeypatch.setattr(
        zones,
        "weather",
        lambda zone, days=3: {
            "hourly": {
                "time": ["2026-11-07T00", "2026-11-07T01", "2026-11-07T02"],
                "wind_speed_100m": [12, 12, 12],
                "shortwave_radiation": [0, 0, 0],
                "cloud_cover": [0, 0, 0],
            }
        },
    )
    monkeypatch.setattr(
        zones,
        "spot",
        lambda zone, date: [
            ("2026-11-07T00:15:00Z", 40.0),
            ("2026-11-07T01:15:00Z", 30.0),
            ("2026-11-07T02:15:00Z", 20.0),
        ],
    )
    r = zones.cf("SE1", "2026-11-07")
    assert r["peak_wind_mw"] == 3144.0 and r["peak_solar_mw"] == 0.0
    assert r["priced_hours"] == 3
    # flat 12 m/s means zero variance, so no correlation is claimed
    assert r["r_wind_prod_spot"] is None


def test_pearson_known_values():
    assert zones._pearson([1, 2, 3], [2, 4, 6]) == 1.0
    assert zones._pearson([1, 2, 3], [6, 4, 2]) == -1.0
    assert zones._pearson([1, 2], [2, 4]) is None  # too few points
    assert zones._pearson([1, 1, 1], [2, 3, 4]) is None  # zero variance


def test_spot_encodes_the_date_and_refuses_a_bad_zone(monkeypatch):
    urls = []
    monkeypatch.setattr(zones, "_json", lambda url: urls.append(url) or {"multiAreaEntries": []})
    zones.spot("SE3", "2026-11-07&evil=1")
    assert "&evil=1" not in urls[0] and "%26evil%3D1" in urls[0] and "deliveryArea=SE3" in urls[0]
    for bad in ("SE3&x=1", "../x", "", "se3"):
        try:
            zones.spot(bad, "2026-11-07")
        except ValueError:
            continue
        raise AssertionError(f"zone {bad!r} was accepted")


def test_an_error_reply_becomes_a_clear_exception(monkeypatch):
    monkeypatch.setattr(zones.sources, "fetch_url", lambda url: "Error: HTTP Error 503")
    try:
        zones.weather("FI")
    except RuntimeError as error:
        assert "HTTP Error 503" in str(error)
    else:
        raise AssertionError("no exception")


def test_correlate_uses_weather_and_prices(monkeypatch):
    hours = [f"2026-11-07T{hour:02d}:00" for hour in range(4)]
    monkeypatch.setattr(
        zones,
        "weather",
        lambda zone, days=1: {
            "hourly": {"time": hours, "cloud_cover": [0, 50, 100, 80], "wind_speed_100m": [2, 4, 6, 8]}
        },
    )
    monkeypatch.setattr(
        zones, "spot", lambda zone, date: [(f"{hour}:00:00Z", 10.0 * (n + 1)) for n, hour in enumerate(hours)]
    )
    result = zones.correlate("FI", "2026-11-07")
    assert result["hours"] == 4 and result["priced_hours"] == 4 and result["r_wind_spot"] == 1.0


def test_zone_table_is_plain_data():
    assert zones.ZONES["FI"].wind_mw == 9535 and zones.ZONES["SE1"].name.startswith("Luleå")
