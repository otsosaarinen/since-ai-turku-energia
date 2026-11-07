"""Guards around model-written code and keys: child environment, redaction, the macOS sandbox, the .env file."""

import os
import subprocess
import sys

import pytest

from harness import envfile, safety, tools

FAKE = {
    "FINGRID_API_KEY": "fake-fingrid-key-0001",
    "ENTSOE_API_KEY": "fake-entsoe-key-0002",
    "OPENROUTER_API_KEY": "fake-openrouter-key-0003",
    "MY_SECRET_TOKEN": "fake-token-0004",
    "AWS_SECRET_ACCESS_KEY": "fake-aws-0005",
}


@pytest.fixture
def fake_keys(monkeypatch):
    for name, value in FAKE.items():
        monkeypatch.setenv(name, value)
    return FAKE


# ---------- the child's environment ----------
def test_child_environment_keeps_only_the_allow_list(fake_keys):
    child = safety.child_environment()
    assert set(child) <= set(safety.CHILD_ENV_ALLOWLIST)
    assert not set(fake_keys) & set(child)
    assert not any("KEY" in name or "TOKEN" in name or "SECRET" in name for name in child)
    assert safety.child_environment({"PATH": "/bin", "FINGRID_API_KEY": "x", "HOME": "/h"}) == {
        "PATH": "/bin",
        "HOME": "/h",
    }


def test_model_written_code_does_not_see_the_keys(fake_keys):
    """The real run_python tool, in a real child process: it must find none of the key-like variables."""
    out = tools.run_python(
        "import os\nprint(sorted(name for name in os.environ if any(w in name for w in ('KEY','TOKEN','SECRET'))))\n"
        "print([v for v in os.environ.values() if v.startswith('fake-')])"
    )
    assert out.splitlines() == ["[]", "[]"]
    for value in fake_keys.values():
        assert value not in out


def test_importing_the_harness_modules_in_the_child_does_not_load_keys(fake_keys):
    """`from harness import zones` pulls in sources.py; that import used to read .env into the child's environment."""
    out = tools.run_python(
        "import os\nfrom harness import zones, sources\n"
        "print(zones.table()[0]['zone'])\nprint(os.environ.get('FINGRID_API_KEY'))"
    )
    assert out.splitlines() == ["SE1", "None"]


def test_run_python_basics(monkeypatch):
    assert tools.run_python("print(6 * 7)") == "42"
    assert tools.run_python("pass") == "(no output)"
    assert "ZeroDivisionError" in tools.run_python("1/0")
    monkeypatch.setattr(tools, "PYTHON_TIMEOUT_S", 1)
    assert tools.run_python("import time; time.sleep(5)") == "Error: timeout (1s)"
    long_output = tools.run_python("print('x' * 100000)")
    assert len(long_output) < tools.MAX_CHARS + 100 and "cut at" in long_output


def test_model_code_cannot_read_stdin_or_hang_on_input():
    assert "EOFError" in tools.run_python("input()")


# ---------- redaction ----------
def test_redact_blanks_every_known_key_value(fake_keys):
    text = "url?securityToken=fake-entsoe-key-0002&x=1 and fake-fingrid-key-0001 and fake-openrouter-key-0003"
    cleaned = safety.redact(text)
    assert all(
        value not in cleaned for value in ("fake-entsoe-key-0002", "fake-fingrid-key-0001", "fake-openrouter-key-0003")
    )
    assert cleaned.count(safety.HIDDEN) == 3
    assert safety.redact("nothing secret here") == "nothing secret here"
    assert safety.redact("short", {"FINGRID_API_KEY": "short"}) == "short"  # too short to be a real key: left alone


# ---------- macOS sandbox ----------
def test_sandbox_profile_text(tmp_path):
    secret = tmp_path / "secret file.env"
    profile = safety.sandbox_profile((secret,), allow_network=False, home=tmp_path)
    assert f'(deny file-read* (literal "{secret}"))' in profile
    assert f'(deny file-read* (subpath "{tmp_path / ".ssh"}"))' in profile
    assert profile.index("(deny file-write*)") < profile.index("(allow file-write*")  # later rules win
    assert "(deny network*)" in profile
    assert "(deny network*)" not in safety.sandbox_profile((), allow_network=True, home=tmp_path)
    assert '\\"' in safety.sandbox_profile(
        (tmp_path / 'we"ird',), home=tmp_path
    )  # quotes in a path cannot break the profile


def test_without_a_sandbox_argv_is_unchanged(monkeypatch):
    monkeypatch.setenv(safety.SANDBOX_DISABLE_ENV, "1")
    assert not safety.sandbox_available()
    assert safety.wrap_in_sandbox(["python", "-"]) == ["python", "-"]


needs_sandbox = pytest.mark.skipif(not safety.sandbox_available(), reason="macOS sandbox-exec not available")


@needs_sandbox
def test_sandboxed_code_cannot_read_the_settings_file_or_write_outside_temp(tmp_path, monkeypatch):
    fake_env = tmp_path / ".env"
    fake_env.write_text("FINGRID_API_KEY=not-a-real-key\n")  # a stand-in: the real .env is never touched by tests
    monkeypatch.setattr(safety, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(safety, "ENV_FILE", fake_env)
    outside = tmp_path.parent / "must_not_exist.txt"  # tmp_path.parent is under the temp folder, so use $HOME instead
    home_file = os.path.expanduser("~/harness_sandbox_test_must_not_exist.txt")
    out = tools.run_python(
        f"""
try:
    open({str(fake_env)!r}).read(); print('READ-OK')
except PermissionError:
    print('read denied')
try:
    open({home_file!r}, 'w'); print('WRITE-OK')
except PermissionError:
    print('write denied')
open({str(tmp_path / "ok.txt")!r}, 'w').write('x'); print('temp write ok')
"""
    )
    assert out.splitlines() == ["read denied", "write denied", "temp write ok"]
    assert not os.path.exists(home_file) and not outside.exists()


@needs_sandbox
def test_the_network_can_be_cut_for_model_code(monkeypatch):
    monkeypatch.setenv(tools.PYTHON_NETWORK_ENV, "0")
    out = tools.run_python(
        "import socket\ntry:\n    socket.create_connection(('127.0.0.1', 9), timeout=2)\n"
        "except OSError as e:\n    print(type(e).__name__)"
    )
    assert "PermissionError" in out or "OSError" in out


# ---------- the .env file ----------
def test_saving_a_key_replaces_the_line_instead_of_duplicating(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# keep me\nFINGRID_API_KEY=old\nENTSOE_API_KEY=e-key-123\nFINGRID_API_KEY=duplicate\n")
    monkeypatch.delenv("FINGRID_API_KEY", raising=False)
    envfile.save_key("FINGRID_API_KEY", "new-key-1", env)
    envfile.save_key("FINGRID_API_KEY", "newer-key-2", env)
    text = env.read_text()
    assert text.count("FINGRID_API_KEY=") == 1 and "FINGRID_API_KEY=newer-key-2" in text
    assert text.splitlines()[0] == "# keep me" and "ENTSOE_API_KEY=e-key-123" in text
    assert (env.stat().st_mode & 0o777) == 0o600
    assert not (tmp_path / ".env.tmp").exists()  # the temporary file is gone after the atomic replace
    fresh = tmp_path / "new.env"  # created with mode 0600 when missing
    envfile.save_key("ENTSOE_API_KEY", "x", fresh)
    assert (fresh.stat().st_mode & 0o777) == 0o600
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)


def test_a_loose_file_mode_is_tightened_on_save(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("A=1\n")
    env.chmod(0o644)
    monkeypatch.delenv("FINGRID_API_KEY", raising=False)
    envfile.save_key("FINGRID_API_KEY", "abc-123-def", env)
    assert (env.stat().st_mode & 0o777) == 0o600


def test_key_values_that_would_not_survive_the_file_are_refused(tmp_path):
    for bad in ("", "  ", "a b", 'q"x', "it's", "a#b", "a\nb", "x" * 301, None, 5):
        with pytest.raises(ValueError):
            envfile.validate_key_value(bad)
        with pytest.raises(ValueError):
            envfile.save_key("FINGRID_API_KEY", bad, tmp_path / ".env")  # type: ignore[arg-type]
    assert not (tmp_path / ".env").exists()


def test_key_status_lists_names_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ENTSOE_API_KEY=abc-123-def\n")
    monkeypatch.delenv("FINGRID_API_KEY", raising=False)
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    assert envfile.key_status(env) == {"set": ["ENTSOE_API_KEY"], "missing": ["FINGRID_API_KEY"]}
    assert "abc-123-def" not in str(envfile.key_status(env))


def test_every_harness_module_imports_cleanly_in_a_fresh_process():
    """Catches import cycles and modules that only worked because another test imported something first."""
    modules = (
        "harness.server, harness.agent, harness.report, harness.zones, harness.tools, harness.jobs, harness.watcher"
    )
    result = subprocess.run(
        [sys.executable, "-c", f"import {modules}"], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
