"""The local control server behind the website's Harness tab (written for this repo; not part of the upstream harness).

    cd backend && uv run --group harness python -m harness.server   (the website reaches it via its /harness-api proxy)

It starts the analyst (agent.py) as a child process for one fixed question, reports its progress and answer, and can
stop it. Because the analyst lets a model run Python on this computer, the server:
  * listens on 127.0.0.1 only,
  * refuses any request whose Host or Origin header is not localhost / 127.0.0.1 (other websites, DNS rebinding),
  * accepts only the fixed questions in presets.py (the page sends a preset id, never text), one job at a time,
  * limits request bodies, times out slow connections, never returns a key value and never shows a traceback.
"""

import json
import logging
import os
import signal
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import FrameType
from typing import Any
from urllib.parse import parse_qs, urlsplit

from src.live_alerts import fetch as fetch_live_alerts

from . import configure_logging, envfile
from .jobs import JobRunner, JobStartError
from .presets import PRESETS, with_context
from .validation import (
    MAX_BODY_BYTES,
    RequestError,
    check_key_request,
    check_run_request,
    host_ok,
    model_allowed,
    origin_ok,
)
from .watcher import AlertWatcher

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LLAMA_URL = "http://localhost:9931/v1"  # the Llama app
DEFAULT_ALERT_POLL_S = 300
MODEL_LIST_TIMEOUT_S = 3
SOCKET_TIMEOUT_S = 15  # a client that stalls mid-request must not hold a thread forever
AUTO_RECALC_ENV = "HARNESS_AUTO_RECALC"  # set to 0 to stop new alerts from starting a run by themselves
FORECAST_PRESET = "imbalance"  # the question rerun automatically when a new alert appears


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        raise SystemExit(f"{name} must be a whole number") from None


def list_models(llama_url: str) -> list[str]:
    """Allowed model ids the local Llama app offers; empty when it is not running."""
    try:
        with urllib.request.urlopen(llama_url.rstrip("/") + "/models", timeout=MODEL_LIST_TIMEOUT_S) as response:
            return [model["id"] for model in json.load(response)["data"] if model_allowed(model["id"])]
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.debug("model list unavailable: %s", error)
        return []


class Panel:
    """Everything the HTTP handler needs in one object, so tests can build a server with temp files and fake jobs."""

    def __init__(
        self, runner: JobRunner, llama_url: str, env_file: Path, alert_poll_seconds: int, alert_fetch=fetch_live_alerts
    ) -> None:
        self.runner = runner
        self.llama_url = llama_url
        self.env_file = env_file
        self.watcher = AlertWatcher(alert_fetch, self._recalculate, alert_poll_seconds)

    def key_status(self) -> dict[str, list[str]]:
        return envfile.key_status(self.env_file)

    def start_run(self, preset_id: str, model: str) -> None:
        """Start a fixed question; raises JobStartError (also when the preset's API key is missing)."""
        needed = PRESETS[preset_id].get("key")
        if needed and needed not in self.key_status()["set"]:
            raise JobStartError(f"set {needed} first (the field above the Start button)")
        self.runner.start(preset_id, with_context(PRESETS[preset_id]["prompt"]), model)

    def _recalculate(self, new_alerts: list[dict]) -> None:
        """A new alert reruns the imbalance forecast on its own, when the model server and the key are there.

        It runs model-written Python with nobody watching, so HARNESS_AUTO_RECALC=0 switches it off.
        """
        if os.environ.get(AUTO_RECALC_ENV) == "0":
            return
        models = list_models(self.llama_url)
        if not models:
            return
        try:
            logger.info("[alerts] %d new (%s), recalculating", len(new_alerts), new_alerts[0].get("title"))
            self.start_run(FORECAST_PRESET, models[0])
        except JobStartError as error:
            logger.info("[alerts] not recalculating: %s", error)

    def info(self) -> dict[str, Any]:
        presets = [{"id": key, "label": value["label"], "about": value["about"]} for key, value in PRESETS.items()]
        return {
            "llama_url": self.llama_url,
            "models": list_models(self.llama_url),
            "presets": presets,
            "keys": self.key_status(),
        }


def make_handler(panel: Panel) -> type[BaseHTTPRequestHandler]:
    """The request handler class bound to one Panel."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "harness-panel"
        timeout = SOCKET_TIMEOUT_S

        def log_message(self, format: str, *args: Any) -> None:  # name fixed by the base class
            logger.debug(format, *args)  # one line per request would flood the terminal

        def _send(self, status: int, payload: object) -> None:
            data = json.dumps(payload).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                logger.debug("client went away before the answer was sent")

        def _guard(self) -> bool:
            if host_ok(self.headers.get("Host")) and origin_ok(self.headers.get("Origin")):
                return True
            self._send(403, {"error": "forbidden"})
            return False

        def _read_json(self) -> object:
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                raise RequestError("send JSON", 415)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise RequestError("bad Content-Length") from None
            if length < 0:
                raise RequestError("bad Content-Length")
            if length > MAX_BODY_BYTES:
                raise RequestError("request too large", 413)
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                raise RequestError("bad JSON") from None

        def _dispatch(self, routes: dict[str, Any]) -> None:
            """Guard, route, and turn every failure into a short JSON error (no tracebacks, no paths)."""
            if not self._guard():
                return
            url = urlsplit(self.path)
            handler = routes.get(url.path)
            if handler is None:
                self._send(404, {"error": "not found"})
                return
            try:
                status, payload = handler(url)
            except RequestError as error:
                status, payload = error.status, {"error": str(error)}
            except JobStartError as error:
                status, payload = 409, {"error": str(error)}
            except Exception:  # the server must keep running; the cause goes to the log, not to the page
                logger.exception("request %s failed", url.path)
                status, payload = 500, {"error": "internal error"}
            self._send(status, payload)

        # --- GET routes ---
        def _get_info(self, _url: Any) -> tuple[int, Any]:
            return 200, panel.info()

        def _get_keys(self, _url: Any) -> tuple[int, Any]:
            return 200, panel.key_status()

        def _get_job(self, url: Any) -> tuple[int, Any]:
            raw = (parse_qs(url.query).get("since") or ["0"])[0] or "0"
            try:
                since = int(raw)
            except ValueError:
                raise RequestError("since must be a whole number") from None
            return 200, {"job": panel.runner.view(since)}

        def _get_alerts(self, _url: Any) -> tuple[int, Any]:
            return 200, {"alerts": panel.watcher.snapshot(), "poll_seconds": panel.watcher.poll_seconds}

        # --- POST routes ---
        def _post_run(self, _url: Any) -> tuple[int, Any]:
            preset, model = check_run_request(self._read_json())
            panel.start_run(preset, model)
            return 200, {"job": panel.runner.view()}

        def _post_keys(self, _url: Any) -> tuple[int, Any]:
            name, value = check_key_request(self._read_json())
            try:
                envfile.save_key(name, value, panel.env_file)
            except OSError:
                logger.exception("could not save the key %s", name)  # the message names the key, never its value
                raise RequestError("could not save the key (see the server's terminal)", 500) from None
            return 200, panel.key_status()

        def _post_stop(self, _url: Any) -> tuple[int, Any]:
            return 200, {"stopped": panel.runner.stop()}

        def do_GET(self) -> None:  # name fixed by the base class
            self._dispatch(
                {
                    "/api/info": self._get_info,
                    "/api/keys": self._get_keys,
                    "/api/job": self._get_job,
                    "/api/alerts": self._get_alerts,
                }
            )

        def do_POST(self) -> None:
            self._dispatch({"/api/run": self._post_run, "/api/keys": self._post_keys, "/api/stop": self._post_stop})

        def _method_not_allowed(self) -> None:
            if self._guard():
                self._send(405, {"error": "method not allowed"})

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _method_not_allowed

    return Handler


def make_server(panel: Panel, port: int) -> ThreadingHTTPServer:
    """A server bound to 127.0.0.1 only (port 0 = any free port)."""
    return ThreadingHTTPServer((HOST, port), make_handler(panel))


def _exit_on_sigterm(signum: int, frame: FrameType | None) -> None:
    """Turn SIGTERM (what `kill` and dev.sh send) into a normal exit, so main() still stops a running job."""
    raise SystemExit(0)


def main() -> None:
    configure_logging()
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    envfile.load_env()  # keys from the settings file into os.environ, never overriding it
    port = _env_int("HARNESS_SERVER_PORT", DEFAULT_PORT)
    llama_url = os.environ.get("LLAMACPP_BASE_URL", DEFAULT_LLAMA_URL)
    panel = Panel(
        JobRunner(llama_url=llama_url), llama_url, envfile.ENV_FILE, _env_int("ALERT_POLL_S", DEFAULT_ALERT_POLL_S)
    )
    stop = threading.Event()
    threading.Thread(target=panel.watcher.run, args=(stop,), daemon=True).start()
    server = make_server(panel, port)
    print(f"Harness panel server on http://{HOST}:{port} (local model at {llama_url}). Ctrl+C stops it.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        panel.runner.stop()
        server.server_close()


if __name__ == "__main__":
    main()
