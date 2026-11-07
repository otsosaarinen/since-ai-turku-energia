"""The three tools the model can call: `run_python`, `fetch_url` and `get_data`, plus their JSON schemas.

`call_tool` never raises: whatever goes wrong comes back as an 'Error: ...' text the model can react to. Every result is
passed through `redact`, so a key value can never reach the model, the progress log or the website.
"""

import itertools
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import BACKEND_DIR, FETCHED_DATA_DIR
from .safety import child_environment, redact, wrap_in_sandbox
from .sources import MAX_CHARS, SOURCES, fetch_url, get_data

logger = logging.getLogger(__name__)

PYTHON_TIMEOUT_S = 30
PREVIEW_CHARS = 1200  # how much of a fetched result the model sees; the rest is in the saved file
MAX_FILE_NAME_CHARS = 40
PYTHON_NETWORK_ENV = "HARNESS_PYTHON_NETWORK"  # set to 0 to cut the network for model-written code (macOS sandbox only)
_file_numbers = itertools.count(1)


class ToolArgumentError(ValueError):
    """The model sent arguments a tool cannot use; the message goes back to the model."""


def _limit(text: str) -> str:
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + f"\n... (output cut at {MAX_CHARS} characters)"


def run_python(code: str) -> str:
    """Run model-written Python in a child process and return what it printed.

    The child gets no API keys (allow-listed environment), reads the code from stdin (not visible in `ps`), runs from
    backend/ so `from harness import zones` works, and on macOS runs inside the sandbox from safety.py.
    """
    argv = wrap_in_sandbox([sys.executable, "-"], allow_network=os.environ.get(PYTHON_NETWORK_ENV) != "0")
    try:
        done = subprocess.run(  # argv is a fixed list; the code travels on stdin, never through a shell
            argv,
            input=code,
            capture_output=True,
            text=True,
            timeout=PYTHON_TIMEOUT_S,
            cwd=BACKEND_DIR,
            env=child_environment(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Error: timeout ({PYTHON_TIMEOUT_S}s)"
    except OSError as error:
        return f"Error: could not run Python: {error}"
    return _limit((done.stdout.strip() + "\n" + done.stderr.strip()).strip()) or "(no output)"


def save_result(text: str, name: str, data_dir: Path = FETCHED_DATA_DIR) -> str:
    """Save a fetched result to a file and return a short preview plus the path.

    The model's code then loads the file instead of containing the data: long pasted JSON made small models write broken
    Python. The file name is built from a counter and the cleaned `name`, so it cannot leave `data_dir`.
    """
    if text.startswith("Error"):
        return text
    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))[:MAX_FILE_NAME_CHARS]
    is_json = text.lstrip()[:1] in ("{", "[")
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{next(_file_numbers)}_{safe_name}.{'json' if is_json else 'txt'}"
    path.write_text(text, encoding="utf-8")
    more = "" if len(text) <= PREVIEW_CHARS else f"\n... ({len(text) - PREVIEW_CHARS} more characters, see the file)"
    loader = f"json.load(open({str(path)!r}))" if is_json else f"open({str(path)!r}).read()"
    return (
        f"{text[:PREVIEW_CHARS]}{more}\n\nThe full result ({len(text)} characters) is saved at {path}. "
        f"In run_python load it with {loader}. Do NOT paste this data into your code."
    )


def _text_argument(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ToolArgumentError(f"argument {name!r} is required and must be text")
    return value


def _run_python_tool(arguments: dict[str, Any]) -> str:
    return run_python(_text_argument(arguments, "code"))


def _fetch_url_tool(arguments: dict[str, Any]) -> str:
    return save_result(fetch_url(_text_argument(arguments, "url")), "fetch_url")


def _get_data_tool(arguments: dict[str, Any]) -> str:
    source = _text_argument(arguments, "source")
    params = arguments.get("params") or {}
    if not isinstance(params, dict):
        raise ToolArgumentError('argument \'params\' must be an object such as {"lat": 60.4, "lon": 22.3}')
    return save_result(get_data(source, params), source)


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "run_python": _run_python_tool,
    "fetch_url": _fetch_url_tool,
    "get_data": _get_data_tool,
}


def call_tool(name: str, arguments: object) -> str:
    """Run a tool by name with already-parsed JSON arguments; always returns text, never raises."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Error: unknown tool {name}"
    if not isinstance(arguments, dict):
        return "Error: the tool arguments must be a JSON object"
    try:
        return redact(handler(arguments))
    except ToolArgumentError as error:
        return f"Error: {error}"
    except Exception as error:  # a failing tool must not end the run: the model gets the error, the log the trace
        logger.exception("tool %s failed", name)
        return redact(f"Error: {name} failed: {error}")


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS = [
    _function(
        "run_python",
        "Execute Python code (pandas, numpy, scipy, statsmodels, sklearn available) and return its output.",
        {"code": {"type": "string"}},
        ["code"],
    ),
    _function(
        "fetch_url",
        "GET a live data endpoint on a Nord Pool source host (HTTP/HTTPS, JSON, CSV, text) and return its body. "
        "Use for current values, then analyse with run_python.",
        {"url": {"type": "string"}},
        ["url"],
    ),
    _function(
        "get_data",
        "Fetch one named Nord Pool data source: " + ", ".join(SOURCES) + ".",
        {
            "source": {"type": "string", "enum": list(SOURCES)},
            "params": {
                "type": "object",
                "description": "source parameters, e.g. {lat, lon} or {in_domain, out_domain, start, end}",
            },
        },
        ["source"],
    ),
]
