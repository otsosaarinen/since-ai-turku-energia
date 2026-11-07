"""harness/sources.py without network: host scope, redirects, parameter encoding, key handling, response shaping."""

import json
import urllib.error
import urllib.request

import pytest

from harness import sources

FAKE_ENTSOE = "fake-entsoe-token-9999"


@pytest.fixture
def recorded(monkeypatch):
    """Replace the network layer; every URL and header set that would have been fetched is recorded."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        sources, "_read_body", lambda url, headers: calls.append((url, headers or {})) or '{"data": []}'
    )
    return calls


# ---------- scope ----------
def test_only_https_on_the_known_hosts_can_be_fetched(recorded):
    for url in (
        "https://evil.example/x",
        "http://data.fingrid.fi/api/datasets/1/data",
        "file:///etc/passwd",
        "ftp://api.met.no/x",
        "data.fingrid.fi/x",
        "",
    ):
        assert sources.fetch_url(url).startswith("Error:"), url
    assert recorded == []  # nothing was sent
    assert sources.fetch_url("https://api.spot-hinta.fi/JustNow") == json.dumps({"data": []}, indent=2)


def test_a_redirect_to_another_host_is_refused():
    handler = sources._ScopedRedirects()
    request = urllib.request.Request("https://data.fingrid.fi/api/x", headers={"x-api-key": "k"})
    for target in (
        "https://evil.example/steal",
        "http://data.fingrid.fi/downgraded",
        "https://data.fingrid.fi.evil.example/x",
    ):
        with pytest.raises(urllib.error.HTTPError):
            handler.redirect_request(request, None, 302, "Found", {}, target)


def test_a_redirect_to_another_allowed_host_does_not_carry_the_key_header():
    handler = sources._ScopedRedirects()
    request = urllib.request.Request("https://data.fingrid.fi/api/x", headers={"x-api-key": "k", "User-Agent": "u"})
    other = handler.redirect_request(request, None, 302, "Found", {}, "https://api.met.no/x")
    assert other is not None and "x-api-key" not in {name.lower() for name in other.headers}
    same = handler.redirect_request(request, None, 302, "Found", {}, "https://data.fingrid.fi/api/y")
    assert same is not None and "x-api-key" in {name.lower() for name in same.headers}


def test_fetch_errors_do_not_leak_the_token(monkeypatch):
    monkeypatch.setenv("ENTSOE_API_KEY", FAKE_ENTSOE)

    def fail(url, headers):
        raise urllib.error.URLError(f"cannot reach {url}")

    monkeypatch.setattr(sources, "_read_body", fail)
    text = sources.fetch_url(f"https://web-api.tp.entsoe.eu/api?securityToken={FAKE_ENTSOE}")
    assert text.startswith("Error:") and FAKE_ENTSOE not in text


# ---------- get_data ----------
def test_get_data_unknown_source_and_missing_key(recorded, monkeypatch):
    monkeypatch.delenv("FINGRID_API_KEY", raising=False)
    assert sources.get_data("nope").startswith("Error: unknown source")
    assert "needs FINGRID_API_KEY" in sources.get_data("fingrid_wind_gen")
    assert recorded == []


def test_get_data_fills_the_window_and_sends_the_key_header(recorded, monkeypatch):
    monkeypatch.setenv("FINGRID_API_KEY", "fake-fingrid-key-0001")
    sources.get_data("fingrid_wind_gen")
    ((url, headers),) = recorded
    assert url.startswith("https://data.fingrid.fi/api/datasets/181/data?startTime=20") and "&endTime=20" in url
    assert headers == {"x-api-key": "fake-fingrid-key-0001"}


def test_get_data_encodes_parameters_so_they_cannot_add_query_fields(recorded, monkeypatch):
    monkeypatch.setenv("FINGRID_API_KEY", "fake-fingrid-key-0001")
    sources.get_data("fingrid_wind_gen", {"start": "2026-11-07T10:00:00+00:00", "end": "x&pageSize=99999&evil=1"})
    ((url, _),) = recorded
    assert "startTime=2026-11-07T10:00:00%2B00:00" in url and "&evil=1" not in url and "%26evil%3D1" in url
    assert url.count("pageSize=") == 1


def test_the_model_cannot_override_the_entsoe_token_or_the_host(recorded, monkeypatch):
    monkeypatch.setenv("ENTSOE_API_KEY", FAKE_ENTSOE)
    sources.get_data(
        "transfer_flow",
        {"token": "model-token", "in_domain": "A", "out_domain": "B", "start": "1", "end": "2", "host": "evil"},
    )
    ((url, _),) = recorded
    assert (
        f"securityToken={FAKE_ENTSOE}" in url
        and "model-token" not in url
        and url.startswith("https://web-api.tp.entsoe.eu/")
    )


def test_get_data_names_the_missing_parameter(recorded):
    assert "needs parameter 'lat'" in sources.get_data("cloud_wind", {"lon": 22})
    assert recorded == []


def test_a_param_called_source_is_just_an_unused_parameter(recorded):
    sources.get_data("spot_price_fi", {"source": "x"})  # used to raise "multiple values for 'source'"
    assert len(recorded) == 1


def test_default_values_of_a_source_are_used(recorded):
    sources.get_data("statnett_reservoir")
    assert recorded[0][0].endswith("/LastWeekData/3")


# ---------- response shaping ----------
def test_long_data_lists_are_thinned_but_keep_the_span():
    rows = [{"t": n, "v": n * 1.5} for n in range(2000)]
    shaped = sources._shorten(json.dumps({"data": rows}))
    kept = json.loads(shaped)["data"]  # still valid JSON: thinning, not cutting
    assert len(shaped) <= sources.MAX_CHARS and 8 < len(kept) < 2000
    assert kept[0]["t"] == 0 and kept[-1]["t"] > 1000


def test_a_top_level_json_list_no_longer_breaks_shaping():
    big_list = [{"zone": n, "text": "x" * 50} for n in range(1000)]
    shaped = sources._shorten(json.dumps(big_list))
    assert shaped.startswith("[") and len(shaped) <= sources.MAX_CHARS


def test_non_json_bodies_are_cut_to_the_reply_limit():
    assert sources._shorten("a,b\n" * 10000) == ("a,b\n" * 10000)[: sources.MAX_CHARS]


def test_every_source_url_is_https_on_an_allowed_host():
    from urllib.parse import urlsplit

    for name, spec in sources.SOURCES.items():
        assert urlsplit(spec["url"]).scheme == "https", name
    assert None not in sources.ALLOWED_HOSTS


# ---------- nordpool_price window ----------
def test_nordpool_price_uses_the_start_and_end_the_model_asks_for(recorded):
    sources.get_data("nordpool_price", {"start": "2026-11-07T00:00:00Z", "end": "2026-11-08T00:00:00Z"})
    ((url, _),) = recorded
    assert url == "https://dashboard.elering.ee/api/nps/price?start=2026-11-07T00:00:00Z&end=2026-11-08T00:00:00Z"


def test_nordpool_price_without_a_window_covers_every_published_hour(recorded):
    from datetime import UTC, datetime, timedelta
    from urllib.parse import parse_qs, unquote, urlsplit

    sources.get_data("nordpool_price")
    ((url, _),) = recorded
    query = parse_qs(urlsplit(unquote(url)).query)
    start = datetime.strptime(query["start"][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    end = datetime.strptime(query["end"][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    now = datetime.now(UTC)
    assert (
        timedelta(minutes=59) < now - start < timedelta(minutes=61)
    )  # one hour back: includes the current quarter-hour
    assert timedelta(hours=47) < end - now < timedelta(hours=49)  # up to everything that is published
