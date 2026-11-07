# Harness (second prediction method)

Copied from https://github.com/rogue-agent/livelectroray at commit b44314d893 (reviewed read-only on 7 Nov 2026; no licence file upstream, ask the author before publishing).
Run it from this folder with the project environment: `uv run --group harness python harness.py -p llamacpp -m <model> -q "<question>"`, see the main README.
Safety: the `run_python` tool runs model-written code with your full user access. Keep API keys out of `key.txt` unless you accept that.
Fingrid key: `harness/key.txt` with a line `FINGRID_API_KEY=...` (git-ignored). Local model: Llama app on `http://localhost:9931/v1`, pass `-m <model id>` (list with `curl localhost:9931/v1/models`).
Test results and limits: `EXPERIMENTS.md` section 8. Do not commit `answer*.txt` or `reports/` (git-ignored).
Changes to the upstream code (copied at b44314d): the files were reformatted by the editor (formatting and unused imports only); `harness.py` got a `--progress` flag (or `HARNESS_PROGRESS=1`)
that prints each turn, tool call and result size to stderr; each answer's ```csv block is written automatically to `reports/prediction.csv` and `reports/prediction.md`
(`report.py answer.txt` does the same offline); a row whose value moved more than 3 % against the previous run is appended, with the answer's prose, to `reports/memory.json`
(a store for the website's server side; nothing displays it yet); the docstring uses uv instead of pip; the CLI asks for missing keys on startup (Enter skips). `server.py` is new (written for this repo):
the local control server used by the website's Harness panel, see the main README; its `/api/keys` endpoint shows which keys are missing and saves the ones typed into the panel to `key.txt` (0600).
