"""The harness control server (harness/server.py + validation.py): who may talk to it, what a request may contain,
what the JSON answers look like (the website relies on these shapes) and that no key value ever leaves it."""

import http.client
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from harness import server, validation
from harness.jobs import JobRunner
from harness.presets import with_context
from harness.validation import RequestError

FAKE_KEY = "TOPSECRETVALUE-123456"
GOOD_MODEL = "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"
ALERTS = [
    {
        "id": "a",
        "kind": "weather",
        "severity": "yellow",
        "title": "storm",
        "detail": "",
        "source": "x",
        "at": None,
        "until": None,
    }
]


# ---------- pure checks ----------
def test_only_this_computer_may_talk_to_the_server():
    for ok in ("localhost:5173", "127.0.0.1:8765", "localhost", "127.0.0.1"):
        assert validation.host_ok(ok), ok
    for bad in (
        None,
        "",
        "evil.com",
        "evil.com:8765",
        "192.168.1.5:5173",
        "localhost.evil.com",
        "localhost.evil.com:80",
    ):
        assert not validation.host_ok(bad), bad
    assert validation.origin_ok(None)
    assert validation.origin_ok("http://localhost:5173") and validation.origin_ok("http://127.0.0.1:5173")
    for bad in ("https://evil.com", "http://localhost.evil.com", "null", "file://"):
        assert not validation.origin_ok(bad), bad


def test_run_request_is_checked():
    assert validation.check_run_request({"preset": "imbalance", "model": GOOD_MODEL}) == ("imbalance", GOOD_MODEL)
    bad_bodies = (
        None,
        [],
        {},
        {"preset": "x", "model": "E4B"},
        {"preset": "imbalance"},
        {"preset": ["imbalance"], "model": "E4B"},
        {"preset": "imbalance", "model": "a b E4B"},
        {"preset": "imbalance", "model": "E4B; rm -rf ~"},
        {"preset": "imbalance", "model": 3},
        {"preset": "imbalance", "model": "-E4B-flag"},
        {"prompt": "do anything", "model": GOOD_MODEL},  # free text is never accepted
    )
    for bad in bad_bodies:
        with pytest.raises(RequestError):
            validation.check_run_request(bad)


def test_every_listed_model_is_allowed_by_default(monkeypatch):
    monkeypatch.delenv("HARNESS_MODEL_FILTER", raising=False)
    for model in (GOOD_MODEL, "ggml-org/gemma-4-12B-it-GGUF:Q8_0", "qwen3:32b"):
        assert validation.model_allowed(model)
        assert validation.check_run_request({"preset": "imbalance", "model": model}) == ("imbalance", model)


def test_a_model_filter_can_still_restrict_the_choice(monkeypatch):
    monkeypatch.setenv("HARNESS_MODEL_FILTER", "E4B")
    assert validation.model_allowed(GOOD_MODEL)
    assert not validation.model_allowed("ggml-org/gemma-4-12B-it-GGUF:Q8_0")
    with pytest.raises(RequestError):
        validation.check_run_request({"preset": "imbalance", "model": "ggml-org/gemma-4-12B-it-GGUF:Q8_0"})


def test_key_request_is_checked_and_never_echoes_the_value():
    for bad in (
        None,
        {},
        {"name": "EVIL_KEY", "value": "x"},
        {"name": "FINGRID_API_KEY", "value": "  "},
        {"name": "FINGRID_API_KEY", "value": "a\nb"},
        {"name": "FINGRID_API_KEY", "value": 3},
        {"name": "FINGRID_API_KEY", "value": "has space"},
        {"name": "FINGRID_API_KEY", "value": 'q"uote'},
        {"name": "FINGRID_API_KEY", "value": "x" * 301},
    ):
        with pytest.raises(RequestError) as caught:
            validation.check_key_request(bad)
        assert "has space" not in str(caught.value)
    assert validation.check_key_request({"name": "FINGRID_API_KEY", "value": " secret "}) == (
        "FINGRID_API_KEY",
        "secret",
    )


def test_the_model_is_told_the_current_time():
    from datetime import UTC, datetime

    text = with_context("Forecast.", datetime(2026, 11, 7, 12, 30, tzinfo=UTC))
    assert "2026-11-07T12:30:00Z" in text and text.endswith("Forecast.") and "never words like 'now'" in text


# ---------- a real server on a free port, with fake jobs, fake alerts and a temporary key file ----------
Request = Callable[..., tuple[int, dict]]


@pytest.fixture
def env_file(tmp_path, monkeypatch) -> Path:
    for name in ("FINGRID_API_KEY", "ENTSOE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / ".env"


@pytest.fixture
def panel(env_file, monkeypatch) -> server.Panel:
    monkeypatch.setattr(server, "list_models", lambda url: ["gemma-E4B"])
    code = (
        "import sys,time; print('[tool] get_data x', file=sys.stderr, flush=True); time.sleep(0.2); print('the answer')"
    )
    runner = JobRunner(build_command=lambda prompt, model: [sys.executable, "-c", code])
    return server.Panel(runner, "http://localhost:9931/v1", env_file, 300, alert_fetch=lambda: ALERTS)


@pytest.fixture
def api(panel) -> Iterator[Request]:
    httpd = server.make_server(panel, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    def request(method: str, path: str, body: object = None, headers: dict | None = None, raw: bytes | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        sent = {"Content-Type": "application/json", **(headers or {})} if payload is not None else dict(headers or {})
        connection.request(method, path, body=payload, headers=sent)
        response = connection.getresponse()
        text = response.read()
        connection.close()
        return response.status, json.loads(text)

    yield request
    panel.runner.stop()
    httpd.shutdown()
    httpd.server_close()


def test_the_server_binds_to_this_computer_only(panel):
    httpd = server.make_server(panel, 0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()


def test_info_keys_and_alerts_have_the_shapes_the_website_reads(api, panel):
    status, info = api("GET", "/api/info")
    assert status == 200 and set(info) == {"llama_url", "models", "presets", "keys"}
    assert info["models"] == ["gemma-E4B"] and set(info["keys"]) == {"set", "missing"}
    assert {p["id"] for p in info["presets"]} == set(server.PRESETS)
    assert all(set(p) == {"id", "label", "about"} for p in info["presets"])
    assert api("GET", "/api/keys") == (200, {"set": [], "missing": ["FINGRID_API_KEY", "ENTSOE_API_KEY"]})
    panel.watcher.poll()
    assert api("GET", "/api/alerts") == (200, {"alerts": ALERTS, "poll_seconds": 300})
    assert api("GET", "/api/job") == (200, {"job": None})


def test_foreign_hosts_and_origins_are_refused_on_every_route(api):
    for method, path in (
        ("GET", "/api/info"),
        ("GET", "/api/keys"),
        ("GET", "/api/job"),
        ("POST", "/api/stop"),
        ("POST", "/api/keys"),
    ):
        assert api(method, path, headers={"Origin": "https://evil.com"})[0] == 403, path
        assert api(method, path, headers={"Host": "evil.com"})[0] == 403, path
        assert api(method, path, headers={"Origin": "http://localhost.evil.com"})[0] == 403, path
    assert api("GET", "/api/keys", headers={"Origin": "http://localhost:5173"})[0] == 200


def test_unknown_routes_and_methods(api):
    assert api("GET", "/api/nothing")[0] == 404
    assert api("POST", "/api/nothing")[0] == 404
    for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
        assert api(method, "/api/keys")[0] == 405, method
    assert api("PUT", "/api/keys", headers={"Origin": "https://evil.com"})[0] == 403  # the guard comes first


def test_request_limits_and_bad_input_give_short_errors(api):
    assert api("POST", "/api/run", raw=b"x" * 20_001)[0] == 413
    assert api("POST", "/api/run", raw=b"not json")[0] == 400
    assert api("POST", "/api/run", headers={"Content-Type": "text/plain"}, raw=b"{}")[0] == 415
    status, body = api(
        "POST", "/api/run", {"preset": "imbalance", "prompt": "free text", "model": "not a valid model id"}
    )
    assert status == 400 and set(body) == {"error"}
    assert api("GET", "/api/job?since=abc")[0] == 400
    assert api("GET", "/api/job?since=-5")[0] == 200  # a negative cursor is treated as 0


def test_a_bad_content_length_is_a_400_not_a_crash(panel):
    httpd = server.make_server(panel, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for length in ("abc", "-1"):
            connection = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
            connection.putrequest("POST", "/api/keys")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", length)
            connection.endheaders()
            assert connection.getresponse().status == 400
            connection.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_keys_are_saved_to_the_file_and_never_returned(api, env_file):
    assert api("POST", "/api/keys", {"name": "EVIL", "value": "x"})[0] == 400
    status, body = api("POST", "/api/keys", {"name": "FINGRID_API_KEY", "value": FAKE_KEY})
    assert status == 200 and body == {"set": ["FINGRID_API_KEY"], "missing": ["ENTSOE_API_KEY"]}
    assert f"FINGRID_API_KEY={FAKE_KEY}" in env_file.read_text()
    assert (env_file.stat().st_mode & 0o777) == 0o600
    everything = json.dumps([api("GET", "/api/info")[1], api("GET", "/api/keys")[1], body])
    assert FAKE_KEY not in everything
    api("POST", "/api/keys", {"name": "FINGRID_API_KEY", "value": "replacement-key-1"})
    assert env_file.read_text().count("FINGRID_API_KEY=") == 1


def test_a_run_needs_its_key_then_runs_and_can_be_polled(api):
    status, body = api("POST", "/api/run", {"preset": "imbalance", "model": GOOD_MODEL})
    assert status == 409 and "FINGRID_API_KEY" in body["error"]
    api("POST", "/api/keys", {"name": "FINGRID_API_KEY", "value": FAKE_KEY})
    status, body = api("POST", "/api/run", {"preset": "imbalance", "model": GOOD_MODEL})
    assert status == 200 and set(body["job"]) == {
        "id",
        "status",
        "model",
        "preset",
        "elapsed",
        "lines",
        "next",
        "answer",
    }
    assert api("POST", "/api/run", {"preset": "dayahead", "model": GOOD_MODEL})[0] == 409  # one job at a time
    job = _wait_for_end(api)
    assert job["status"] == "done" and job["answer"].strip() == "the answer"
    assert any("[tool] get_data" in line for line in job["lines"])
    assert api("GET", f"/api/job?since={job['next']}")[1]["job"]["lines"] == []  # the cursor returns only new lines


def _wait_for_end(api: Request) -> dict:
    deadline = time.time() + 15
    while time.time() < deadline:
        job = api("GET", "/api/job")[1]["job"]
        if job and job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not end")


def test_stop_endpoint(api, panel):
    panel.runner._build_command = lambda prompt, model: [sys.executable, "-c", "import time; time.sleep(60)"]
    assert api("POST", "/api/stop") == (200, {"stopped": False})
    api("POST", "/api/keys", {"name": "FINGRID_API_KEY", "value": FAKE_KEY})
    api("POST", "/api/run", {"preset": "imbalance", "model": GOOD_MODEL})
    assert api("POST", "/api/stop") == (200, {"stopped": True})
    assert _wait_for_end(api)["status"] == "stopped"


def test_an_unexpected_error_gives_a_plain_500_without_details(api, panel, monkeypatch):
    def boom() -> dict:
        raise RuntimeError("secret path /Users/someone/.env")

    monkeypatch.setattr(panel, "key_status", boom)
    status, body = api("GET", "/api/keys")
    assert status == 500 and body == {"error": "internal error"}


def test_saving_a_key_that_cannot_be_written_is_a_clean_500(api, panel, tmp_path):
    panel.env_file = tmp_path / "no_such_folder" / ".env"
    status, body = api("POST", "/api/keys", {"name": "FINGRID_API_KEY", "value": FAKE_KEY})
    assert status == 500 and FAKE_KEY not in json.dumps(body) and "no_such_folder" not in json.dumps(body)


# ---------- reacting to new alerts ----------
def test_a_new_alert_starts_the_forecast_once(panel, monkeypatch):
    started = []
    monkeypatch.setattr(panel, "start_run", lambda preset, model: started.append((preset, model)))
    assert panel.watcher.poll() == ALERTS  # the first poll sees everything as new
    panel.watcher.step()  # same ids again: nothing new, no run
    assert started == []
    panel._recalculate([{"id": "z", "title": "new"}])
    assert started == [("imbalance", "gemma-E4B")]


def test_recalculation_waits_when_the_model_server_or_key_is_missing(panel, monkeypatch):
    monkeypatch.setattr(server, "list_models", lambda url: [])
    panel._recalculate([{"id": "z", "title": "new"}])  # no model: nothing happens, no error
    monkeypatch.setattr(server, "list_models", lambda url: ["gemma-E4B"])
    panel._recalculate([{"id": "z", "title": "new"}])  # no FINGRID key: start_run refuses, which is only logged
    assert panel.runner.view() is None


def test_automatic_reruns_can_be_switched_off(panel, monkeypatch):
    started = []
    monkeypatch.setattr(panel, "start_run", lambda preset, model: started.append(preset))
    monkeypatch.setenv(server.AUTO_RECALC_ENV, "0")
    panel._recalculate([{"id": "z", "title": "new"}])
    assert started == []
    monkeypatch.delenv(server.AUTO_RECALC_ENV)
    panel._recalculate([{"id": "z", "title": "new"}])
    assert started == ["imbalance"]


def test_env_loading_never_overrides_the_environment(tmp_path, monkeypatch):
    from harness import envfile

    env = tmp_path / ".env"
    env.write_text("# comment\n\nFINGRID_API_KEY=\"from-file\"\nexport ENTSOE_API_KEY='e-file'\n")
    monkeypatch.setenv("FINGRID_API_KEY", "from-env")
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    envfile.load_env(env)
    assert os.environ["FINGRID_API_KEY"] == "from-env" and os.environ["ENTSOE_API_KEY"] == "e-file"
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
