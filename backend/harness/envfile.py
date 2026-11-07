"""The project's ONE settings file: `.env` in the repository root (template `.env.example`).

NAME=value lines; `#` comments, blank lines, `export ` and matching quotes are allowed.
Real environment variables always win.
Both the website's key fields (via the server) and the command line save keys through `save_key` here.
"""

import os
import re
import threading
from pathlib import Path

from .paths import REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"
API_KEY_NAMES = ("FINGRID_API_KEY", "ENTSOE_API_KEY")  # keys the website may set (the server only uses a local model)
SECRET_NAMES = (*API_KEY_NAMES, "OPENROUTER_API_KEY")  # every variable whose value must never reach model-written code
MAX_KEY_LENGTH = 300
_KEY_VALUE_RE = re.compile(
    r"^[\w.~+/=:\-]+$"
)  # no spaces, quotes or '#', so the value survives a round trip through .env
_EXPORT_PREFIX = "export "
_save_lock = threading.Lock()  # two requests saving at once must not lose each other's line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _strip_export(line: str) -> str:
    return line[len(_EXPORT_PREFIX) :].lstrip() if line.startswith(_EXPORT_PREFIX) else line


def parse(path: Path) -> dict[str, str]:
    """NAME -> value from a settings file ({} if it does not exist)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = _strip_export(line).partition("=")
        if separator:
            values[name.strip()] = _unquote(value)
    return values


def load_env(path: Path | None = None) -> None:
    """Put the file's keys into os.environ without overriding variables that are already set."""
    for name, value in parse(path or ENV_FILE).items():
        if name and value:
            os.environ.setdefault(name, value)


def validate_key_value(value: object) -> str:
    """The cleaned key text, or ValueError saying what is wrong (the message never contains the value)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("key is empty")
    value = value.strip()
    if len(value) > MAX_KEY_LENGTH or not _KEY_VALUE_RE.match(value):
        raise ValueError("key has odd characters")
    return value


def key_status(path: Path | None = None) -> dict[str, list[str]]:
    """Which website keys exist, by name only (never values): {"set": [...], "missing": [...]}."""
    saved = parse(path or ENV_FILE)
    present = [name for name in API_KEY_NAMES if os.environ.get(name) or saved.get(name)]
    return {"set": present, "missing": [name for name in API_KEY_NAMES if name not in present]}


def _assigns(line: str, name: str) -> bool:
    """True when the line is an active `NAME=...` assignment (not a comment)."""
    stripped = _strip_export(line.strip())
    variable, separator, _ = stripped.partition("=")
    return bool(separator) and not stripped.startswith("#") and variable.strip() == name


def _replace_assignment(lines: list[str], name: str, new_line: str) -> list[str]:
    """Replace the first assignment of NAME by new_line, drop later duplicates, append when there was none."""
    result: list[str] = []
    done = False
    for line in lines:
        if not _assigns(line, name):
            result.append(line)
        elif not done:
            result.append(new_line)
            done = True
    return result if done else [*result, new_line]


def save_key(name: str, value: str, path: Path | None = None) -> None:
    """Write NAME=value into the settings file (mode 0600, replacing an existing line) and into os.environ.

    The file is replaced atomically, so a crash halfway cannot leave it empty and lose the other keys.
    """
    value = validate_key_value(value)
    path = path or ENV_FILE
    with _save_lock:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        updated = _replace_assignment(lines, name, f"{name}={value}")
        temporary = path.with_name(path.name + ".tmp")
        file_descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(updated) + "\n")
        temporary.chmod(0o600)
        temporary.replace(path)
    os.environ[name] = value
