"""Input checks for the control server, as plain functions: who may talk to it and what a request may contain."""

import os
import re
from urllib.parse import urlsplit

from .envfile import API_KEY_NAMES, validate_key_value
from .presets import PRESETS

LOCAL_NAMES = frozenset({"localhost", "127.0.0.1"})
MODEL_RE = re.compile(
    r"^[A-Za-z0-9][\w./:\-]{0,199}$"
)  # starts with a letter or digit so it can never look like a command-line flag
# Only the light model is offered and accepted. HARNESS_MODEL_FILTER = comma-separated words, one must be in the id.
DEFAULT_MODEL_FILTER = "E4B"
MAX_BODY_BYTES = 20_000


class RequestError(Exception):
    """A refused request; `status` is the HTTP status and the message is safe to show (it never holds a key)."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def model_filter() -> list[str]:
    raw = os.environ.get("HARNESS_MODEL_FILTER", DEFAULT_MODEL_FILTER)
    return [word.strip().lower() for word in raw.split(",") if word.strip()]


def model_allowed(model_id: str) -> bool:
    words = model_filter()
    return not words or any(word in model_id.lower() for word in words)


def host_ok(host_header: str | None) -> bool:
    """The Host header must name this computer; a DNS-rebinding attack arrives under another name."""
    if not host_header:
        return False
    name = host_header.rsplit(":", 1)[0].strip("[]") if ":" in host_header else host_header
    return name in LOCAL_NAMES


def origin_ok(origin: str | None) -> bool:
    """No Origin (same-origin request, curl) is fine; a page from another site is not."""
    if not origin:
        return True
    return (urlsplit(origin).hostname or "") in LOCAL_NAMES


def check_run_request(body: object) -> tuple[str, str]:
    """Validate a start request and return (preset id, model); raises RequestError. Free text is never accepted."""
    if not isinstance(body, dict):
        raise RequestError("body must be a JSON object")
    preset, model = body.get("preset"), body.get("model")
    if not isinstance(preset, str) or preset not in PRESETS:
        raise RequestError("unknown preset")
    if not isinstance(model, str) or not MODEL_RE.match(model):
        raise RequestError("model name is missing or has odd characters")
    if not model_allowed(model):
        raise RequestError(f"only models matching {model_filter()} are allowed (set HARNESS_MODEL_FILTER to change)")
    return preset, model


def check_key_request(body: object) -> tuple[str, str]:
    """Validate a key save request and return (name, value); raises RequestError without ever quoting the value."""
    if not isinstance(body, dict):
        raise RequestError("body must be a JSON object")
    name = body.get("name")
    if name not in API_KEY_NAMES:
        raise RequestError(f"unknown key name; use one of: {', '.join(API_KEY_NAMES)}")
    try:
        return name, validate_key_value(body.get("value"))
    except ValueError as error:
        raise RequestError(str(error)) from error
