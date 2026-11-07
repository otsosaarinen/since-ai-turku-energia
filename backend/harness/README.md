# Harness (the second prediction method)

- A small AI language model runs locally (through the Llama app) and acts as an analyst. The LightGBM model stays the entry.
- On "Start" the website sends one of two fixed questions (`imbalance`, `dayahead`) to a local server, `server.py` (127.0.0.1:8765).
- The server starts `agent.py`. The model calls tools: it fetches live public data (Fingrid, Elering, Nord Pool, Statnett, Open-Meteo, ...)
  and writes small Python programs (`run_python`).
- The answer is a short text plus a csv table; the website draws it as a chart.
- It is a live demo, not a backtest: a small model with naive reasoning, so its numbers are weak (`EXPERIMENTS.md` section 8).

```
Browser -> Next.js proxy /harness-api -> server.py (127.0.0.1:8765) -> agent.py (child process)
                                                                         |-> Llama app (localhost:9931), the model
                                                                         |-> fetch_url / get_data -> public data services
                                                                         '-> run_python -> grandchild Python process (the risky part)
```

## Files

| File | What it does |
|---|---|
| `server.py` | Local web server for the website (`/api/info`, `/api/keys`, `/api/job`, `/api/run`, `/api/stop`, `/api/alerts`). |
| `validation.py` | Input checks: allowed Host/Origin, what a run request or key may contain. |
| `presets.py` | The two fixed questions. The website sends only a preset name, never free text. |
| `jobs.py` | Starts the agent as a child process, collects progress lines and the answer, stops it. One job at a time, 20 minute limit. |
| `watcher.py` | Polls four public alert feeds every 5 minutes and reports each new alert once. |
| `agent.py` | The analyst: loop "ask model, run its tool calls, repeat" (at most 10 tool turns; a broken tool call gets 4 extra retries). Also a command line tool. |
| `tools.py` | The three tools `run_python`, `fetch_url`, `get_data`. Long data is saved under `reports/data/`; the model sees a 1200-character preview and the path. |
| `sources.py` | The data services (`SOURCES`) and the code that fetches them safely. |
| `prompts.py` | The system prompt and the exact csv format of the answer. |
| `zones.py` | Wind/solar capacity per Nord Pool zone and helper maths (`from harness import zones`). Hard-coded 2025-26 numbers that will age. |
| `report.py` | Cuts the csv table from an answer into `reports/prediction.csv` and `.md`; keeps `reports/memory.json`. |
| `safety.py` | Protection around model-written code: scrubbed environment, key redaction, macOS sandbox. |
| `envfile.py`, `paths.py` | Read/write the root `.env` (API keys); where things live on disk. |
| `reports/`, `answer.txt` | Output and a test leftover (both git-ignored). |

Alert code outside this folder: `backend/src/live_alerts.py` turns the four feeds (MET Norway warnings, GDACS, Caruna power cuts,
Open-Meteo wind) into a short list shown on the Harness tab and, for a new alert, reruns the imbalance forecast by itself.
`backend/src/alerts.py` is separate: it writes supervisor alerts from the LightGBM spike probabilities (used by `scripts/export_web_data.py`).

## Run

From `backend/`:

```
uv sync --group harness
uv run --group harness python -m harness.server        # the server the website uses
uv run --group harness python -m harness.agent -p llamacpp -m <model id> -q "<question>" --progress
uv run python -m harness.report answer.txt             # redo reports/ from a saved answer
uv run pytest -q tests/test_harness_*.py               # no network, model or keys needed
```

The root `./dev.sh` starts this server together with the website. The Llama app must run on `http://localhost:9931/v1`
(list models: `curl localhost:9931/v1/models`; every listed model is offered).
API keys (`FINGRID_API_KEY`, `ENTSOE_API_KEY`): copy `.env.example` (repository root) to `.env`, or type them into the website's
Settings box (the server saves them to `.env`, mode 0600).

Optional environment variables:

- `HARNESS_SERVER_PORT` (default 8765), `LLAMACPP_BASE_URL`, `HARNESS_MODEL_FILTER` (default empty = no restriction; e.g. `E4B,12B` limits the list), `ALERT_POLL_S` (default 300).
- `HARNESS_AUTO_RECALC=0`: new alerts no longer start a run by themselves.
- `HARNESS_NO_SANDBOX=1`: run model code without the macOS sandbox.
- `HARNESS_PYTHON_NETWORK=0`: cut the network for model code (macOS sandbox only; `zones.cf()` and urllib then stop working).
- `HARNESS_PROGRESS=1`: same as `--progress`.

The progress lines `[turn k/n]`, `[tool] ...`, `[result] N characters: ...`, `[think] ...`, `[done]`, `[stop]` printed by `agent.py`
are parsed by `frontend/src/features/harness/lib/progressSteps.ts`. Do not change their format.

## Safety

The agent lets a model run Python on this computer, and the model reads web data that a stranger can write into
(prompt injection). What protects you:

- The server listens on 127.0.0.1 only, refuses any Host or Origin that is not localhost, accepts only fixed questions,
  one job at a time, bodies up to 20 kB, and never returns a key value or a stack trace.
- Model code gets no API keys (allow-listed environment; `sources.py` does not read `.env` on import).
- On macOS model code runs in `sandbox-exec`: it cannot read `.env*` in the repository root, `~/.ssh`, `~/.aws`, `~/.gnupg`,
  `~/.config/gh` or the keychain folder, and can write only to temp folders. On other systems only the key scrubbing applies.
- Known key values in tool results, progress lines and answers are replaced by `[hidden]`.
- `fetch_url` and `get_data` speak https only, to the hosts in `SOURCES`; foreign redirects are refused, key headers are not forwarded,
  saved file names cannot leave `reports/data/`.
- Stopping or timing out a job kills the agent and its Python process.

Not solved: model code can still use the network and read your other files (outside the macOS blocklist).
Keep the model small and local, and do not run the harness where you cannot afford a leak.

## Known weak spots

- `memory.json` (kept when a forecast row moves over 3 % between runs, last 200 entries) is written but nothing reads it.
- The `ollama` and `openrouter` providers and the interactive prompt in `agent.py` work only from the command line.
- The Imbalance preset is too much for a small model (gemma E4B): its Python misreads the layout of the saved data files, the six data fetches leave
  few of the 10 tool calls for retries, and a failed calculation still ends in an answer (every hourly value clamped to 400). The Day-ahead preset
  works and matches the real prices. Ideas if it matters: drop the two fetches the calculation does not need (`spot_price_fi`, `fingrid_consumption`),
  or do the arithmetic in a helper module instead of in model-written code. A larger model is untested.
- The saved data files hold the thinned data (every second row for long feeds), not the full response.
- A small model (gemma E4B) often miscalculates or invents numbers when a step fails; a larger one helps; every model the Llama app lists can be picked.
- Reformatted by the editor (formatting and unused imports only); docstring says uv instead of pip.
- `--progress`: prints each turn, tool call and result size to stderr, plus the model's reasoning as `[think]` lines.
- A tool call with invalid JSON arguments no longer crashes the run; such retries have their own budget (4).
- `get_data` and `fetch_url` results are saved to `reports/data/`; the model gets a preview and the path.
- Each answer's csv block is written to `reports/prediction.csv` and `.md`; rows that moved over 3 % go to `reports/memory.json`.
- Horizon changed from 24 h hourly + 7 d daily to 24 h hourly + 10 d daily; the `drivers` column is one line, parts joined by ` ; `.
- New files written for this repo: `server.py`, `presets.py`, `jobs.py`, `watcher.py`, `validation.py`, `safety.py`, `envfile.py`, `paths.py`.
- 8 Nov 2026, restructure and security pass: `harness/` became a package (`python -m harness.server`, `python -m harness.agent`);
  `harness.py` became `agent.py`, tools moved to `tools.py`, the system prompt to `prompts.py`. Model code gets no keys and a macOS sandbox,
  its output is cut at 20,000 characters; `fetch_url` is https-only; `get_data` takes `params` as one dictionary;
  stop and timeout kill the whole process group; `.env` is saved atomically; `HARNESS_AUTO_RECALC=0` was added;
  the dead `AREAS` list and the unused `ahead` option were removed. API keys now live in the root `.env`, not `harness/key.txt`.
- 8 Nov 2026, teammate's commit "0.6" carried into the new structure and improved: a hard cap of `MAX_TOOL_CALLS = 10` tool calls per question
  that also holds inside one turn (the teammate's version only checked between turns; extra calls now get an error result);
  the imbalance prompt uses the live spot price (`spot_price_fi`, field `PriceNoTax`, never the taxed one) and the realised spot of the last 24 h;
  `nordpool_price` now really takes `start`/`end` (the prompt relied on it, but the URL had no placeholders; default window: 1 h back to 48 h ahead).
- 8 Nov 2026, after the first real run: `sources._shorten` thinned only a list directly under `data`, but the Elering feed nests its lists
  (`data.fi`, `data.ee`, ...), so long answers were cut at 20,000 characters and the saved data file was invalid JSON (the model's Python
  could not load it and it then invented numbers). It now thins the longest list anywhere, keeps the last row and keeps the JSON valid.
  The imbalance prompt got a worked unit example (0.00586 EUR/kWh = 5.86 EUR/MWh) after the small model got it wrong by 10x.
- 8 Nov 2026: the model filter no longer defaults to `E4B`: all models listed by the Llama app can be chosen in the panel and are accepted by the server (the model id is still checked for odd characters; `HARNESS_MODEL_FILTER` can restrict it again).
- 8 Nov 2026, after a run with a larger model also gave a flat forecast: the price feed behind `nordpool_price` lists Estonia first, then
  Finland, Latvia and Lithuania, and models took the first (or last) list for Finland (Estonia was at about 195-200 EUR/MWh while Finland
  was at about 6). `nordpool_price` now returns only one area, `fi` by default (`area` = `ee`, `lv` or `lt` on request; an unknown area gives
  an error naming the valid ones). The imbalance prompt no longer forbids the published day-ahead prices: each hourly row now uses that
  hour's own Finland spot price plus the corrected spread, so the forecast follows the shape of the spot prices instead of one flat level.
