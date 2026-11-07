"""Job lifecycle with a stand-in child process: results, stopping, failure, timeout, redaction and limits."""

import os
import signal
import sys
import time

import pytest

from harness import jobs
from harness.jobs import JobRunner, JobStartError


def runner_for(code: str, **kwargs) -> JobRunner:
    return JobRunner(build_command=lambda prompt, model: [sys.executable, "-c", code], **kwargs)


def wait_until_ended(runner: JobRunner, timeout: float = 15) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        view = runner.view()
        if view and view["status"] != "running":
            return view
        time.sleep(0.05)
    raise AssertionError("job did not end")


def test_a_job_collects_progress_lines_and_the_answer():
    runner = runner_for("import sys; print('[tool] get_data x', file=sys.stderr, flush=True); print('the answer')")
    assert runner.view() is None
    runner.start("imbalance", "prompt", "model-1")
    view = wait_until_ended(runner)
    assert view["status"] == "done" and view["answer"].strip() == "the answer" and view["model"] == "model-1"
    assert view["lines"][0] == "[start] model model-1" and "[tool] get_data x" in view["lines"]
    assert runner.view(since=view["next"])["lines"] == [] and runner.view(since=-3)["lines"] == view["lines"]


def test_only_one_job_runs_at_a_time():
    runner = runner_for("import time; time.sleep(30)")
    runner.start("a", "p", "m")
    with pytest.raises(JobStartError, match="already in progress"):
        runner.start("b", "p", "m")
    assert runner.stop() is True
    assert wait_until_ended(runner)["status"] == "stopped" and runner.stop() is False
    runner.start("c", "p", "m")  # after the stop a new job may start
    runner.stop()
    wait_until_ended(runner)


def test_a_failing_child_is_an_error_and_a_missing_program_is_reported():
    runner = runner_for("import sys; sys.exit(3)")
    runner.start("a", "p", "m")
    assert wait_until_ended(runner)["status"] == "error"
    missing = JobRunner(build_command=lambda prompt, model: ["/no/such/program"])
    missing.start("a", "p", "m")
    view = wait_until_ended(missing)
    assert view["status"] == "error" and any(line.startswith("[error] could not start") for line in view["lines"])


def test_a_job_that_runs_too_long_is_killed():
    runner = runner_for("import time; time.sleep(60)", timeout_s=0.5)
    runner.start("a", "p", "m")
    view = wait_until_ended(runner)
    assert view["status"] == "error" and any("[stop] stopped after" in line for line in view["lines"])


def test_stop_also_ends_what_the_child_started(tmp_path):
    """The agent's run_python child must not keep running after a stop (the whole process group gets the signal)."""
    pid_file = tmp_path / "grandchild.pid"
    code = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    runner = runner_for(code)
    runner.start("a", "p", "m")
    deadline = time.time() + 10
    while not pid_file.exists() and time.time() < deadline:
        time.sleep(0.05)
    time.sleep(0.2)
    grandchild = int(pid_file.read_text())
    runner.stop()
    wait_until_ended(runner)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return  # gone, as wanted
        time.sleep(0.05)
    os.kill(grandchild, signal.SIGKILL)  # do not leave it behind if the assertion below fails
    raise AssertionError("the grandchild process survived the stop")


def test_key_values_are_removed_from_lines_and_answer(monkeypatch):
    monkeypatch.setenv("FINGRID_API_KEY", "fake-fingrid-key-0001")
    runner = runner_for(
        "import sys; print('boom fake-fingrid-key-0001', file=sys.stderr); print('answer fake-fingrid-key-0001')"
    )
    runner.start("a", "p", "m")
    view = wait_until_ended(runner)
    assert "fake-fingrid-key-0001" not in str(view) and "[hidden]" in view["answer"]


def test_long_lines_are_shortened_but_reasoning_is_kept_whole():
    code = "import sys; print('x' * 5000, file=sys.stderr); print('[think] ' + 'y' * 5000, file=sys.stderr)"
    runner = runner_for(code)
    runner.start("a", "p", "m")
    lines = wait_until_ended(runner)["lines"]
    assert max(len(line) for line in lines if not line.startswith("[think]")) <= jobs.LINE_CHARS
    assert any(line.startswith("[think]") and len(line) > 5000 for line in lines)


def test_the_number_of_stored_lines_is_capped(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_LINES", 20)
    runner = runner_for("import sys\nfor n in range(100): print(n, file=sys.stderr)")
    runner.start("a", "p", "m")
    lines = wait_until_ended(runner)["lines"]
    assert len(lines) == 21 and "too many progress lines" in lines[-1]


def test_the_agent_command_line_shape():
    command = jobs.agent_command("question", "gemma-E4B")
    assert command[1:3] == ["-m", "harness.agent"] and command[-1] == "--progress"
    assert command[command.index("-q") + 1] == "question" and command[command.index("-m", 3) + 1] == "gemma-E4B"
