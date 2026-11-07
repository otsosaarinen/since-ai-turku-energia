"""Runs the analyst as a child process for the website, one job at a time, and lets the page watch and stop it.

The child is `python -m harness.agent ... --progress`. Its stderr lines (progress) are collected as the job's lines, its
stdout is the answer. Everything stored is passed through `redact`, so a key value can never reach the page.
"""

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import IO, Any

from .paths import BACKEND_DIR
from .safety import redact

JOB_TIMEOUT_S = 20 * 60
LINE_CHARS = 600
THINK_LINE_CHARS = 20_000  # the model's reasoning is shown in full
THINK_PREFIX = "[think] "
MAX_LINES = 5_000
MAX_ANSWER_CHARS = 1_000_000
JOIN_WAIT_S = 2
CommandBuilder = Callable[[str, str], list[str]]


class JobStartError(Exception):
    """A job cannot start now (one is already running); the message is safe to show."""


@dataclass
class Job:
    id: str
    preset: str
    model: str
    prompt: str
    status: str = "running"  # running | done | error | stopped
    started: float = field(default_factory=time.time)
    ended: float | None = None
    lines: list[str] = field(default_factory=list)
    answer: str = ""
    stop_requested: bool = False
    process: "subprocess.Popen[str] | None" = None


def agent_command(prompt: str, model: str) -> list[str]:
    """The command line that runs one question through the analyst against the local llama.cpp server."""
    return [sys.executable, "-m", "harness.agent", "-p", "llamacpp", "-m", model, "-q", prompt, "--progress"]


def _signal_group(process: "subprocess.Popen[str]", signal_number: int) -> None:
    """Signal the agent and what it started (its run_python child too); the agent runs in its own process group."""
    with contextlib.suppress(ProcessLookupError, PermissionError):  # already gone, which is what we wanted
        os.killpg(process.pid, signal_number)


class JobRunner:
    """Holds the current (or last) job. All state changes happen under one lock."""

    def __init__(
        self, build_command: CommandBuilder = agent_command, llama_url: str = "", timeout_s: float = JOB_TIMEOUT_S
    ) -> None:
        self._build_command = build_command
        self._llama_url = llama_url
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._job: Job | None = None

    def start(self, preset: str, prompt: str, model: str) -> None:
        """Start a job in the background; raises JobStartError when one is already running."""
        with self._lock:
            if self._job and self._job.status == "running":
                raise JobStartError("a run is already in progress")
            job = Job(
                id=uuid.uuid4().hex[:8], preset=preset, model=model, prompt=prompt, lines=[f"[start] model {model}"]
            )
            self._job = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()

    def stop(self) -> bool:
        """Ask the running job to stop; False when nothing is running."""
        with self._lock:
            job = self._job
            if not job or job.status != "running":
                return False
            job.stop_requested = True
            process = job.process
        if process:
            _signal_group(process, signal.SIGTERM)
        return True

    def view(self, since: int = 0) -> dict[str, Any] | None:
        """The job as the website sees it: status, lines from index `since`, the next cursor, the answer."""
        with self._lock:
            job = self._job
            if not job:
                return None
            end = job.ended or time.time()
            return {
                "id": job.id,
                "status": job.status,
                "model": job.model,
                "preset": job.preset,
                "elapsed": round(end - job.started, 1),
                "lines": job.lines[max(0, since) :],
                "next": len(job.lines),
                "answer": job.answer,
            }

    def _append_line(self, job: Job, line: str) -> None:
        text = redact(line.rstrip("\n"))
        text = text[: THINK_LINE_CHARS if text.startswith(THINK_PREFIX) else LINE_CHARS]
        with self._lock:
            if len(job.lines) < MAX_LINES:
                job.lines.append(text)
            elif len(job.lines) == MAX_LINES:
                job.lines.append("[stop] too many progress lines; the rest is not shown")

    def _fail(self, job: Job, message: str) -> None:
        with self._lock:
            job.lines.append(f"[error] {redact(message)}")
            job.status, job.ended = "error", time.time()

    def _run(self, job: Job) -> None:
        env = {**os.environ, "HARNESS_PROVIDER": "llamacpp", "PYTHONUNBUFFERED": "1", "HARNESS_NO_KEYS": "1"}
        if self._llama_url:
            env["LLAMACPP_BASE_URL"] = self._llama_url
        try:
            process = subprocess.Popen(
                self._build_command(job.prompt, job.model),
                cwd=BACKEND_DIR,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except OSError as error:
            self._fail(job, f"could not start: {error}")
            return
        with self._lock:
            job.process = process
            stop_early = job.stop_requested  # a stop that arrived before the process existed
        if stop_early:
            _signal_group(process, signal.SIGTERM)
        answer_parts: list[str] = []
        readers = [
            threading.Thread(target=self._read_progress, args=(job, process.stderr), daemon=True),
            threading.Thread(target=self._read_answer, args=(process.stdout, answer_parts), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            process.wait(timeout=self._timeout_s)
        except subprocess.TimeoutExpired:
            _signal_group(process, signal.SIGKILL)
            process.wait()
            self._append_line(job, f"[stop] stopped after {int(self._timeout_s) // 60} minutes")
        for reader in readers:
            reader.join(JOIN_WAIT_S)
        with self._lock:
            job.answer = redact("".join(answer_parts))
            job.status = "stopped" if job.stop_requested else ("done" if process.returncode == 0 else "error")
            job.ended = time.time()
            job.process = None

    def _read_progress(self, job: Job, stream: IO[str] | None) -> None:
        for line in stream or ():
            self._append_line(job, line)

    @staticmethod
    def _read_answer(stream: IO[str] | None, parts: list[str]) -> None:
        size = 0
        for chunk in stream or ():  # keep draining past the cap so the child never blocks on a full pipe
            if size < MAX_ANSWER_CHARS:
                parts.append(chunk)
                size += len(chunk)
