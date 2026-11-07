"""The analyst loop and its command line: ask a model a question, let it call tools, print its answer.

    uv run --group harness python -m harness.agent -p llamacpp -m MODEL -q "question" [--progress]

Needs `uv sync --group harness`. Every provider speaks the OpenAI API. The final answer goes alone to stdout; with
`--progress` (or HARNESS_PROGRESS=1) one line per step goes to stderr. The website's progress list parses those lines
(frontend/src/features/harness/lib/progressSteps.ts), so their format is fixed:

    [turn k/n] ...   [tool] name arguments   [result] N characters: 'text'
    [think] "json string"   [done] ...   [stop] ...

Each answer's csv table is also written to reports/prediction.csv and .md (report.py).
"""

import argparse
import csv
import getpass
import json
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from openai import BadRequestError, InternalServerError, OpenAI, OpenAIError

from . import configure_logging
from .envfile import API_KEY_NAMES, ENV_FILE, load_env, save_key, validate_key_value
from .paths import REPORTS_DIR
from .prompts import SYSTEM_PROMPT
from .report import write_reports
from .tools import TOOLS, call_tool

logger = logging.getLogger(__name__)

PROVIDER_URLS = {
    "ollama": ("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "llamacpp": ("LLAMACPP_BASE_URL", "http://localhost:8081/v1"),
    "openrouter": (None, "https://openrouter.ai/api/v1"),
}
PROVIDER_MODELS = {  # "" -> ask the running server what it loaded
    "ollama": ("OLLAMA_MODEL", "gemma4:e4b"),
    "llamacpp": ("LLAMACPP_MODEL", ""),
    "openrouter": ("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
}
DEFAULT_PROVIDER = "ollama"
MAX_TURNS = 10  # tool-call budget per question
MAX_BROKEN_CALLS = 4  # cut-off tool calls get their own small budget; they do not use up the tool turns
PROGRESS_ARGS_CHARS = 400
PROGRESS_RESULT_CHARS = 200
BROKEN_CALL_HINT = (
    "Your last tool call was cut off and could not be read. Try again with a much shorter call: "
    "at most 40 lines of Python and no long data lists."
)
Progress = Callable[[str], None]


def make_progress(enabled: bool) -> Progress:
    """A logger for the progress lines: stderr when enabled, otherwise it does nothing."""

    def progress(line: str) -> None:
        if enabled:
            print(line, file=sys.stderr, flush=True)

    return progress


def provider_url(provider: str) -> str:
    env_name, default = PROVIDER_URLS[provider]
    return os.environ.get(env_name, default) if env_name else default


def make_client(provider: str, model_arg: str = "") -> tuple[OpenAI, str]:
    """(client, model). OpenRouter needs OPENROUTER_API_KEY; that key goes to OpenRouter only."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if provider == "openrouter" and not api_key:
        sys.exit("OPENROUTER_API_KEY is not set")
    base_url = provider_url(provider)
    client = OpenAI(base_url=base_url, api_key=api_key if provider == "openrouter" else provider)
    env_name, default = PROVIDER_MODELS[provider]
    model = model_arg or os.environ.get(env_name, default)
    if not model:  # llama.cpp: whatever the running server has loaded (the FIRST listed model)
        try:
            model = client.models.list().data[0].id
        except (OpenAIError, IndexError) as error:
            sys.exit(f"no model given and no usable server at {base_url} ({error}); start llama.cpp or pass -m")
    return client, model


def prompt_for_missing_keys(provider: str) -> None:
    """Ask on the terminal for keys that are not set (Enter skips) and save them to the settings file."""
    if os.environ.get("HARNESS_NO_KEYS"):
        return
    names = [
        name
        for name in (*API_KEY_NAMES, "OPENROUTER_API_KEY")
        if name != "OPENROUTER_API_KEY" or provider == "openrouter"
    ]
    missing = [name for name in names if not os.environ.get(name)]
    if not sys.stdin.isatty():  # no terminal to ask in: say what is missing instead of failing silently later
        if missing:
            logger.warning(
                "no terminal to ask for keys; missing %s (add NAME=value lines to %s)", ", ".join(missing), ENV_FILE
            )
        return
    for name in missing:
        try:
            typed = getpass.getpass(f"{name} (Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if typed:
            try:
                save_key(name, validate_key_value(typed))
            except ValueError as error:
                logger.warning("%s not saved: %s", name, error)


def _reasoning_of(message: Any) -> str:
    """The model's own reasoning for this step (llama.cpp calls the field reasoning_content, others reasoning)."""
    return (getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or "").strip()


def _one_line(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ")


def _run_tool_calls(message: Any, messages: list[Any], progress: Progress) -> None:
    """Execute every tool call of `message` and append the results for the model."""
    messages.append(message)
    for call in message.tool_calls:
        progress(f"[tool] {call.function.name} {_one_line(call.function.arguments[:PROGRESS_ARGS_CHARS])}")
        try:
            arguments = json.loads(call.function.arguments)
        except ValueError as error:  # small models sometimes cut their own JSON off: tell the model, let it retry
            result = f"Error: the tool arguments were not valid JSON ({error}). Send a shorter, complete call."
        else:
            result = call_tool(call.function.name, arguments)
        progress(f"[result] {len(result)} characters: {result[:PROGRESS_RESULT_CHARS]!r}")
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})


def chat(client: OpenAI, model: str, messages: list[Any], progress: Progress) -> str:
    """One question: loop model turn -> tool calls -> model turn until it answers or the budgets run out."""
    turn = broken = 0
    while turn < MAX_TURNS:
        turn += 1
        progress(f"[turn {turn}/{MAX_TURNS}] asking the model")
        try:
            response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        except (InternalServerError, BadRequestError) as error:
            # llama.cpp answers 500 when the model's own tool-call JSON is cut off: tell the model and let it retry
            progress(
                f"[result] 0 characters: 'Error: the model sent a broken tool call ({_one_line(str(error)[:300])})'"
            )
            broken += 1
            if broken > MAX_BROKEN_CALLS:
                progress("[stop] the model kept sending broken tool calls")
                return "(the model kept sending broken tool calls; try again or use a larger model)"
            turn -= 1
            messages.append({"role": "user", "content": BROKEN_CALL_HINT})
            continue
        message = response.choices[0].message
        reasoning = _reasoning_of(message)
        if reasoning:  # one JSON line for the website's "thinking" windows
            progress("[think] " + json.dumps(reasoning))
        if message.tool_calls:
            _run_tool_calls(message, messages, progress)
            continue
        progress("[done] final answer received")
        answer = message.content or ""
        messages.append({"role": "assistant", "content": answer})
        return answer
    progress("[stop] tool turn budget used up")
    return "(max tool turns reached)"


def export(answer: str) -> str:
    """Write the answer's csv table to reports/prediction.{csv,md}; a failure is reported but never loses the answer."""
    try:
        csv_path, md_path = write_reports(answer, REPORTS_DIR)
        logger.info("wrote %s and %s", csv_path, md_path)
        if len(csv_path.read_text(encoding="utf-8").splitlines()) < 2:
            logger.info("report: the answer had no csv table, so prediction.csv has only the header")
    except (OSError, ValueError, csv.Error) as error:
        logger.warning("report: %s", error)
    return answer


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m harness.agent", description="Local AI analyst for the Nord Pool market."
    )
    parser.add_argument(
        "-p",
        "--provider",
        default=os.environ.get("HARNESS_PROVIDER", DEFAULT_PROVIDER),
        help=f"one of {', '.join(PROVIDER_URLS)}",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="",
        help="model id (default: the provider's, or the first one a llama.cpp server lists)",
    )
    parser.add_argument(
        "-q", "--prompt", default="", help="one-shot: ask this, print the answer, exit (otherwise an interactive loop)"
    )
    parser.add_argument("--progress", action="store_true", default=os.environ.get("HARNESS_PROGRESS") == "1")
    args = parser.parse_args(argv)
    if args.provider not in PROVIDER_URLS:  # also catches a bad HARNESS_PROVIDER, which argparse's `choices` would not
        parser.error(f"unknown provider {args.provider!r}; use one of: {', '.join(PROVIDER_URLS)}")
    return args


def _ask(client: OpenAI, model: str, question: str, progress: Progress) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    return export(chat(client, model, messages, progress))


def main(argv: list[str] | None = None) -> None:
    """Command line entry: one-shot with -q, otherwise a prompt loop."""
    configure_logging()
    args = parse_args(argv)
    load_env()  # keys from the settings file; the real environment wins
    prompt_for_missing_keys(args.provider)
    client, model = make_client(args.provider, args.model)
    progress = make_progress(args.progress)
    if args.prompt:
        print(_ask(client, model, args.prompt, progress))
        return
    print(f"Stats harness -> {args.provider} · {model} @ {provider_url(args.provider)}")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("quit", "exit", "q"):
            break
        if question:
            print(f"\nassistant> {_ask(client, model, question, progress)}\n")


if __name__ == "__main__":
    main()
