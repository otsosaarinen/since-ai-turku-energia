"""
harness.py — minimal AI harness for statistics & prediction
Usage: uv run --group harness python harness.py [-p ollama|llamacpp|openrouter] [-m MODEL]
Deps:  uv sync --group harness (openai, pandas, numpy, scipy, statsmodels, scikit-learn)
Live data sources and the Nord Pool scope live in sources.py. Each answer's fenced csv block is
also written to reports/prediction.csv and reports/prediction.md; a value that moved more than
3 % against the previous run keeps its reasoning in reports/memory.json (see report.py).
"""

import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

from openai import OpenAI
from sources import SOURCES, SYSTEM, fetch_url, get_data
from report import write_reports

# ─── Config ───────────────────────────────────────────────
BASE_URLS = {  # every provider speaks the OpenAI API
    "ollama": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "llamacpp": os.environ.get("LLAMACPP_BASE_URL", "http://localhost:8081/v1"),
    "openrouter": "https://openrouter.ai/api/v1",
}
MODELS = {  # "" → ask the running server what it loaded
    "ollama": os.environ.get("OLLAMA_MODEL", "gemma4:e4b"),
    "llamacpp": os.environ.get("LLAMACPP_MODEL", ""),
    "openrouter": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
}
MODEL = ""  # set by main()
MAX_TURNS = 10  # tool-call budget per user message
PROGRESS = "--progress" in sys.argv or os.environ.get("HARNESS_PROGRESS") == "1"


def log(msg: str) -> None:
    """Progress lines go to stderr (the final answer stays alone on stdout). Used by the website panel."""
    if PROGRESS:
        print(msg, file=sys.stderr, flush=True)


# ─── Tool: run_python ─────────────────────────────────────
def run_python(code: str) -> str:
    """Execute Python in a subprocess, capture stdout/stderr."""
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        return (out + "\n" + err).strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: timeout (30s)"
    except Exception as e:
        return f"Error: {e}"


FUNCS = {  # tool name → handler(args dict)
    "run_python": lambda a: run_python(a["code"]),
    "fetch_url": lambda a: fetch_url(a["url"]),
    "get_data": lambda a: get_data(a["source"], **a.get("params", {})),
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code (pandas, numpy, scipy, statsmodels, sklearn available) and return its output.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "GET a live data endpoint on a Nord Pool source host (HTTP/HTTPS, JSON, CSV, text) and return its body. Use for current values, then analyse with run_python.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data",
            "description": "Fetch one named Nord Pool data source: "
            + ", ".join(SOURCES)
            + ".",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "enum": list(SOURCES)},
                    "params": {
                        "type": "object",
                        "description": "source parameters, e.g. {lat, lon} or {in_domain, out_domain, start, end}",
                    },
                },
                "required": ["source"],
            },
        },
    },
]


# ─── Client ───────────────────────────────────────────────
def flag(name: str, short: str) -> str:
    """--name v | --name=v | -s v from argv, else ""."""
    a = sys.argv[1:]
    for i, tok in enumerate(a):
        if tok in (name, short):
            return a[i + 1] if i + 1 < len(a) else ""
        if tok.startswith(name + "="):
            return tok.split("=", 1)[1]
    return ""


def pick_provider() -> str:
    """--provider/-p, else HARNESS_PROVIDER, else ollama."""
    p = flag("--provider", "-p") or os.environ.get("HARNESS_PROVIDER", "ollama")
    if p not in BASE_URLS:
        sys.exit(f"unknown provider {p!r}; use one of: {', '.join(BASE_URLS)}")
    return p


KEYFILE = Path(__file__).with_name("key.txt")


def ask_keys(provider: str) -> None:
    """Ask for missing keys before the first request; Enter skips. Saved to key.txt (0600)."""
    if os.environ.get("HARNESS_NO_KEYS") or not sys.stdin.isatty():
        return
    for name in ("OPENROUTER_API_KEY", "FINGRID_API_KEY", "ENTSOE_API_KEY"):
        if name == "OPENROUTER_API_KEY" and provider != "openrouter":
            continue
        if os.environ.get(name):
            continue
        try:
            v = getpass.getpass(f"{name} (Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not v:
            continue
        os.environ[name] = v
        fd = os.open(KEYFILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(f"{name}={v}\n")


def make_client(provider: str) -> tuple[OpenAI, str]:
    """(client, model); openrouter needs OPENROUTER_API_KEY in env."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if provider == "openrouter" and not key:
        sys.exit("OPENROUTER_API_KEY is not set")
    client = OpenAI(base_url=BASE_URLS[provider], api_key=key or provider)
    model = flag("--model", "-m") or MODELS[provider]
    if not model:  # llama.cpp: whatever the running server has loaded
        try:
            model = client.models.list().data[0].id
        except Exception as e:
            sys.exit(
                f"no model given and no server at {BASE_URLS[provider]} ({e}); "
                "start llama.cpp or pass -m"
            )
    return client, model


client: OpenAI = None  # set by main()


def chat(messages: list) -> str:
    """One LLM turn; handles tool calls in a loop up to MAX_TURNS."""
    for turn in range(1, MAX_TURNS + 1):
        log(f"[turn {turn}/{MAX_TURNS}] asking the model")
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                fn = FUNCS.get(tc.function.name)
                log(f"[tool] {tc.function.name} {tc.function.arguments[:400]}")
                result = (
                    fn(json.loads(tc.function.arguments))
                    if fn
                    else f"Error: unknown tool {tc.function.name}"
                )
                log(f"[result] {len(result)} characters: {result[:200]!r}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
        else:
            log("[done] final answer received")
            messages.append({"role": "assistant", "content": msg.content})
            return msg.content
    log("[stop] tool turn budget used up")
    return "(max tool turns reached)"

def export(answer: str) -> str:
    """Write the answer's fenced csv block to reports/prediction.{csv,md}; return the answer."""
    try:
        c, m = write_reports(answer, Path(__file__).with_name("reports"))
        print(f"wrote {c} and {m}", file=sys.stderr)
    except Exception as e:
        print(f"report: {e}", file=sys.stderr)
    return answer

# ─── REPL ─────────────────────────────────────────────────
def main():
    global client, MODEL
    provider = pick_provider()
    one = flag("--prompt", "-q")            # one-shot: ask, print the answer, exit
    ask_keys(provider)                      # no-op without a tty
    client, MODEL = make_client(provider)
    if one:
        print(export(chat([{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": one}])))
        return
    print(f"Stats harness → {provider} · {MODEL} @ {BASE_URLS[provider]}")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in ("quit", "exit", "q"):
            break
        if not user:
            continue
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ]
        print(f"\nassistant> {export(chat(messages))}\n")


if __name__ == "__main__":
    main()
