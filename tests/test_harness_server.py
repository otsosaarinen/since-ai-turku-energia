"""Tests for harness/server.py (the local control server behind the website's Harness panel): who may talk to it, input checks, job lifecycle."""
import importlib.util
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harness_server", ROOT / "harness" / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules["harness_server"] = server
spec.loader.exec_module(server)


def test_only_this_computer_may_talk_to_the_server():
    for ok in ("localhost:5173", "127.0.0.1:8765", "localhost", "127.0.0.1"):
        assert server.host_ok(ok), ok
    for bad in (None, "", "evil.com", "evil.com:8765", "192.168.1.5:5173", "localhost.evil.com"):
        assert not server.host_ok(bad), bad
    assert server.origin_ok(None)
    assert server.origin_ok("http://localhost:5173") and server.origin_ok("http://127.0.0.1:5173")
    assert not server.origin_ok("https://evil.com") and not server.origin_ok("http://localhost.evil.com")


def test_run_request_is_checked():
    assert server.check_run_request({"preset": "imbalance", "model": "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"}) == ("imbalance", "ggml-org/gemma-4-E4B-it-GGUF:Q8_0")
    for bad in (None, [], {}, {"preset": "x", "model": "E4B"}, {"preset": "imbalance"}, {"preset": "imbalance", "model": "a b E4B"},
                {"preset": "imbalance", "model": "E4B; rm -rf ~"}, {"preset": "imbalance", "model": 3},
                {"prompt": "do anything", "model": "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"}):   # free text is never accepted
        assert isinstance(server.check_run_request(bad), str), bad


def test_only_the_light_model_is_allowed():
    assert server.model_allowed("ggml-org/gemma-4-E4B-it-GGUF:Q8_0")
    assert not server.model_allowed("ggml-org/gemma-4-12B-it-GGUF:Q8_0")
    assert not server.model_allowed("Qwen/Qwen3-1.7B-GGUF:Q8_0")
    assert isinstance(server.check_run_request({"preset": "imbalance", "model": "ggml-org/gemma-4-12B-it-GGUF:Q8_0"}), str)


def test_the_model_is_told_the_current_time():
    from datetime import datetime, timezone
    text = server.with_context("Forecast.", datetime(2026, 11, 7, 12, 30, tzinfo=timezone.utc))
    assert "2026-11-07T12:30:00Z" in text and text.endswith("Forecast.") and "never words like 'now'" in text
    assert server.build_cmd("Forecast.", "m")[-2].endswith("Forecast.")


def _wait(pred, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(autouse=True)
def fresh_state():
    server.JOB = None
    yield
    server.stop_job()


def test_job_lifecycle_with_a_stand_in_for_the_harness(monkeypatch):
    code = "import sys,time; print('[tool] get_data x', file=sys.stderr, flush=True); time.sleep(0.2); print('the answer')"
    monkeypatch.setattr(server, "build_cmd", lambda prompt, model: [sys.executable, "-c", code])
    job = server.start_job("imbalance", "m")
    assert isinstance(job, dict)
    assert server.start_job("dayahead", "m") == "a run is already in progress"
    assert _wait(lambda: server.job_view()["status"] != "running")
    v = server.job_view()
    assert v["status"] == "done" and v["answer"].strip() == "the answer"
    assert any("[tool] get_data" in line for line in v["lines"])
    assert server.job_view(since=v["next"])["lines"] == []          # polling with the cursor returns only new lines


def test_stop_ends_a_running_job(monkeypatch):
    monkeypatch.setattr(server, "build_cmd", lambda prompt, model: [sys.executable, "-c", "import time; time.sleep(60)"])
    server.start_job("imbalance", "m")
    assert _wait(lambda: server.JOB.get("proc") is not None)
    assert server.stop_job() is True
    assert _wait(lambda: server.job_view()["status"] == "stopped")
    assert server.stop_job() is False


def test_failed_job_is_reported(monkeypatch):
    monkeypatch.setattr(server, "build_cmd", lambda prompt, model: [sys.executable, "-c", "import sys; sys.exit(3)"])
    server.start_job("imbalance", "m")
    assert _wait(lambda: server.job_view()["status"] != "running")
    assert server.job_view()["status"] == "error"
