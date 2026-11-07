#!/bin/bash
# Start the local control server for the website's Harness panel (http://127.0.0.1:8765, Ctrl+C stops it).
# Needs a local model server (the Llama app on port 9931 by default; override with LLAMACPP_BASE_URL).
# It lets the website start harness.py runs, which execute model-written Python on this computer: use it only on your own laptop.
set -e
cd "$(dirname "$0")/.."
uv sync --group harness
exec uv run --group harness python harness/server.py
