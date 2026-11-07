# Harness (second prediction method)

Copied from https://github.com/rogue-agent/livelectroray at commit b44314d893 (reviewed read-only on 7 Nov 2026; no licence file upstream, ask the author before publishing).
Run it from this folder with the project environment: `uv run --group harness python harness.py -p llamacpp -m <model> -q "<question>"`, see the main README.
Safety: the `run_python` tool runs model-written code with your full user access. Keep API keys out of `key.txt` unless you accept that.
