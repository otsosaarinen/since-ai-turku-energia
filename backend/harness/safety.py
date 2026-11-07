"""Guards around model-written code (the `run_python` tool).

The model may run any Python on this computer, and the model reads web data that an attacker can write into
(prompt injection). Three layers limit the damage:

1. `child_environment` hands the child only a short allow-list of variables, so API keys never reach it.
2. `redact` blanks known key values in anything that is shown to the model or the website.
3. On macOS `wrap_in_sandbox` runs the child under `sandbox-exec` with a profile that hides the settings file and the
   usual secret folders, forbids writing outside temp folders and can cut the network. Other systems get layers 1-2.
"""

import logging
import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from .envfile import ENV_FILE, SECRET_NAMES
from .paths import REPO_ROOT

logger = logging.getLogger(__name__)

CHILD_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TZ")
MIN_REDACTED_LENGTH = 6  # shorter values would blank ordinary words; real keys are far longer
HIDDEN = "[hidden]"
SANDBOX_DISABLE_ENV = "HARNESS_NO_SANDBOX"  # set to 1 to run model code without the macOS sandbox
SANDBOX_EXE = "sandbox-exec"
WRITABLE_PATHS = (
    "/private/tmp",
    "/private/var/folders",
)  # temp folders (macOS resolves /tmp and /var through /private)
WRITABLE_DEVICES = ("/dev/null", "/dev/tty", "/dev/dtracehelper")
SECRET_HOME_FOLDERS = (".ssh", ".aws", ".gnupg", ".config/gh", "Library/Keychains")
_warned_no_sandbox = False


def child_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Only the allow-listed variables of `base` (default: this process); everything else, keys included, is dropped."""
    source = os.environ if base is None else base
    return {name: source[name] for name in CHILD_ENV_ALLOWLIST if name in source}


def redact(text: str, environment: Mapping[str, str] | None = None) -> str:
    """Replace every known secret value in `text` by [hidden]; values come from the environment (default: ours)."""
    source = os.environ if environment is None else environment
    for name in SECRET_NAMES:
        secret = source.get(name, "")
        if len(secret) >= MIN_REDACTED_LENGTH:
            text = text.replace(secret, HIDDEN)
    return text


def _quoted(path: str | Path) -> str:
    """A path as a sandbox-profile string literal."""
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def sandbox_profile(
    secret_files: tuple[Path, ...] = (), *, allow_network: bool = True, home: Path | None = None
) -> str:
    """The macOS sandbox profile: later rules win, so writes are denied first and then allowed for temp folders only."""
    home = home or Path.home()
    rules = ["(version 1)", "(allow default)"]
    rules += [f"(deny file-read* (literal {_quoted(path)}))" for path in secret_files]
    rules += [f"(deny file-read* (subpath {_quoted(home / folder)}))" for folder in SECRET_HOME_FOLDERS]
    rules.append("(deny file-write*)")
    allowed = [f"(subpath {_quoted(path)})" for path in WRITABLE_PATHS] + [
        f"(literal {_quoted(d)})" for d in WRITABLE_DEVICES
    ]
    rules.append(f"(allow file-write* {' '.join(allowed)})")
    if not allow_network:
        rules.append("(deny network*)")
    return "\n".join(rules)


def sandbox_available() -> bool:
    """True on macOS with sandbox-exec present and not switched off by HARNESS_NO_SANDBOX=1."""
    return (
        sys.platform == "darwin"
        and shutil.which(SANDBOX_EXE) is not None
        and os.environ.get(SANDBOX_DISABLE_ENV) != "1"
    )


def wrap_in_sandbox(argv: list[str], *, allow_network: bool = True) -> list[str]:
    """Prefix argv with sandbox-exec when available; otherwise return it unchanged (and say so once)."""
    global _warned_no_sandbox
    if not sandbox_available():
        if not _warned_no_sandbox:
            logger.warning(
                "no sandbox for model-written code on this system: only the key scrubbing protects your files"
            )
            _warned_no_sandbox = True
        return argv
    secret_files = tuple(dict.fromkeys([*sorted(REPO_ROOT.glob(".env*")), ENV_FILE]))  # every .env* file, once each
    profile = sandbox_profile(secret_files, allow_network=allow_network)
    return [shutil.which(SANDBOX_EXE) or SANDBOX_EXE, "-p", profile, *argv]
