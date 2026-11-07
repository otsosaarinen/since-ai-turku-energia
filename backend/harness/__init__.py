"""The Harness: a small local AI analyst (second prediction method) and the server behind the website's Harness tab.

Start the server from backend/ with `uv run --group harness python -m harness.server`; see README.md in this folder.
"""

import logging
import sys


def configure_logging() -> None:
    """Plain messages on stderr: our own INFO lines and everyone's warnings (HTTP libraries stay quiet at INFO)."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
    logging.getLogger(__name__).setLevel(logging.INFO)
