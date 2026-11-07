"""server.py: small local control server for the website's Harness panel.

Starts harness.py as a subprocess for one prompt, reports its progress and answer, and can stop it. Written for this repo (not part of the
upstream harness). Start it with `./scripts/start_harness.sh` (or `uv run --group harness python harness/server.py`); the website reaches it
through the Vite dev proxy at /harness-api.

Safety: harness.py lets a model run Python on this computer, so this server
  * listens on 127.0.0.1 only,
  * refuses requests whose Host or Origin header is not localhost / 127.0.0.1 (blocks other websites and DNS rebinding),
  * runs one job at a time, accepts only the fixed prompts in PRESETS (the browser sends a preset name, never text) and stops a job after 20 minutes.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("HARNESS_SERVER_PORT", "8765"))
LLAMA_URL = os.environ.get("LLAMACPP_BASE_URL", "http://localhost:9931/v1")
# The prompts live here, not in the browser: a run executes model-written Python, so the website can only choose one of these.
PRESETS = {
    "imbalance": {
        "label": "Imbalance price, next 12 h",
        "about": "Day-ahead price plus the typical spread (imbalance minus day-ahead) of the last 5 hours of real prices.",
        "prompt": (
            "Forecast the Finnish imbalance price for every 2 hours of the next 12 hours (6 rows, starting at the next full hour). Follow these steps exactly. "
            "1) get_data nordpool_price: take the Finland day-ahead spot price for each of those hours. "
            "2) get_data fingrid_imbalance_price with start = 5 hours ago and end = now (ISO8601 UTC): you get about 20 quarter-hour prices. "
            "Pair them with the spot price of the same quarter-hour and compute the spread = imbalance price minus spot, then its median, 10th and 90th percentile with run_python. "
            "3) Forecast for each hour = spot of that hour + median spread; low = spot + 10th percentile spread; high = spot + 90th percentile spread. "
            "Do NOT extrapolate a trend line. Clamp all values to -50..400 EUR/MWh. "
            "4) End with the csv block, horizon=24h, metric=imbalance_price, one row per 2 hours. Keep the explanation under 10 lines. Only use hours later than the current time."
        ),
    },
    "dayahead": {
        "label": "Day-ahead price, next 12 h",
        "about": "Lists the published day-ahead prices of the next hours. No forecasting.",
        "prompt": (
            "Get nordpool_price and list the Finland day-ahead price for every 2 hours of the next 12 hours starting at the next full hour. "
            "Do not invent any numbers. Only list hours later than the current time. End with the csv block inside a ```csv code fence, "
            "horizon=24h, metric=spot_price, low=high=value, drivers=nordpool_price."
        ),
    },
}
TIMEOUT_S = 20 * 60
LOCAL_NAMES = {"localhost", "127.0.0.1"}
MODEL_RE = re.compile(r"^[\w./:\-]{1,200}$")
# Only the light model is offered and accepted. HARNESS_MODEL_FILTER = comma-separated words, a model id must contain one (case-insensitive).
MODEL_FILTER = [w.strip().lower() for w in os.environ.get("HARNESS_MODEL_FILTER", "E4B").split(",") if w.strip()]


def model_allowed(model_id: str) -> bool:
    return not MODEL_FILTER or any(w in model_id.lower() for w in MODEL_FILTER)

LOCK = threading.Lock()
JOB: dict | None = None  # the current or last job


def host_ok(host_header: str | None) -> bool:
    """Host header must name this computer (a rebinding attack arrives with another name)."""
    if not host_header:
        return False
    return host_header.rsplit(":", 1)[0].strip("[]") in LOCAL_NAMES if ":" in host_header else host_header in LOCAL_NAMES


def origin_ok(origin: str | None) -> bool:
    """No Origin (same-origin GET, curl) is fine; a browser page from another site is not."""
    if not origin:
        return True
    return (urlsplit(origin).hostname or "") in LOCAL_NAMES


def check_run_request(body: object) -> tuple[str, str] | str:
    """Validate a start request. Returns (preset id, model) or an error message."""
    if not isinstance(body, dict):
        return "body must be a JSON object"
    preset, model = body.get("preset"), body.get("model")
    if preset not in PRESETS:
        return "unknown preset"
    if not isinstance(model, str) or not MODEL_RE.match(model):
        return "model name is missing or has odd characters"
    if not model_allowed(model):
        return f"only models matching {MODEL_FILTER} are allowed (set HARNESS_MODEL_FILTER to change)"
    return preset, model


def with_context(prompt: str, now: datetime | None = None) -> str:
    """Small models do not know the time and pass words like 'now' as a time window: give them the real time and the format."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"Current time (UTC): {stamp}. In get_data params always use ISO8601 UTC timestamps such as {stamp}, "
            "never words like 'now' or '5 hours ago' (compute them from the current time above). Only forecast hours later than the current time. Put the csv table inside a ```csv code fence, with times as ISO8601 UTC.\n\n" + prompt)


def build_cmd(prompt: str, model: str) -> list[str]:
    return [sys.executable, str(HERE / "harness.py"), "-p", "llamacpp", "-m", model, "-q", with_context(prompt), "--progress"]


def _run_job(job: dict) -> None:
    env = {**os.environ, "HARNESS_PROVIDER": "llamacpp", "LLAMACPP_BASE_URL": LLAMA_URL, "PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(
            build_cmd(job["prompt"], job["model"]), cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except OSError as e:
        with LOCK:
            job.update(status="error", ended=time.time(), lines=job["lines"] + [f"[error] could not start: {e}"])
        return
    job["proc"] = proc
    out: list[str] = []

    def read_err():
        for line in proc.stderr:
            with LOCK:
                job["lines"].append(line.rstrip("\n")[:600])

    t_err = threading.Thread(target=read_err, daemon=True)
    t_err.start()
    t_out = threading.Thread(target=lambda: out.extend(proc.stdout), daemon=True)
    t_out.start()
    try:
        proc.wait(timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        with LOCK:
            job["lines"].append(f"[stop] stopped after {TIMEOUT_S // 60} minutes")
    t_err.join(2)
    t_out.join(2)
    with LOCK:
        job["answer"] = "".join(out)
        stopped = job.get("stop_requested")
        job["status"] = "stopped" if stopped else ("done" if proc.returncode == 0 else "error")
        job["ended"] = time.time()
        job.pop("proc", None)


def start_job(preset: str, model: str) -> dict | str:
    global JOB
    with LOCK:
        if JOB and JOB["status"] == "running":
            return "a run is already in progress"
        JOB = {
            "id": uuid.uuid4().hex[:8], "status": "running", "preset": preset, "prompt": PRESETS[preset]["prompt"], "model": model,
            "started": time.time(), "ended": None, "lines": [f"[start] model {model}"], "answer": "",
        }
        job = JOB
    threading.Thread(target=_run_job, args=(job,), daemon=True).start()
    return job


def stop_job() -> bool:
    with LOCK:
        job = JOB
        if not job or job["status"] != "running":
            return False
        job["stop_requested"] = True
        proc = job.get("proc")
    if proc:
        proc.terminate()
    return True


def job_view(since: int = 0) -> dict | None:
    with LOCK:
        if not JOB:
            return None
        end = JOB["ended"] or time.time()
        return {
            "id": JOB["id"], "status": JOB["status"], "model": JOB["model"], "preset": JOB["preset"],
            "elapsed": round(end - JOB["started"], 1), "lines": JOB["lines"][since:], "next": len(JOB["lines"]), "answer": JOB["answer"],
        }


def list_models() -> list[str]:
    try:
        with urllib.request.urlopen(LLAMA_URL.rstrip("/") + "/models", timeout=3) as r:
            return [m["id"] for m in json.load(r)["data"] if model_allowed(m["id"])]
    except Exception:
        return []


class Handler(BaseHTTPRequestHandler):
    server_version = "harness-panel"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code: int, obj: object) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _guard(self) -> bool:
        if not host_ok(self.headers.get("Host")) or not origin_ok(self.headers.get("Origin")):
            self._send(403, {"error": "forbidden"})
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        url = urlsplit(self.path)
        if url.path == "/api/info":
            self._send(200, {"llama_url": LLAMA_URL, "models": list_models(), "presets": [{"id": k, "label": v["label"], "about": v["about"]} for k, v in PRESETS.items()]})
        elif url.path == "/api/job":
            since = int((parse_qs(url.query).get("since") or ["0"])[0] or 0)
            self._send(200, {"job": job_view(since)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._guard():
            return
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > 20000:
            return self._send(413, {"error": "request too large"})
        raw = self.rfile.read(length) if length else b""
        if url.path == "/api/run":
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._send(415, {"error": "send JSON"})
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad JSON"})
            checked = check_run_request(body)
            if isinstance(checked, str):
                return self._send(400, {"error": checked})
            started = start_job(*checked)
            if isinstance(started, str):
                return self._send(409, {"error": started})
            self._send(200, {"job": job_view()})
        elif url.path == "/api/stop":
            self._send(200, {"stopped": stop_job()})
        else:
            self._send(404, {"error": "not found"})


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Harness panel server on http://127.0.0.1:{PORT} (local model at {LLAMA_URL}). Ctrl+C stops it.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        stop_job()


if __name__ == "__main__":
    main()
