"""Tests for harness/harness.py's tool budget: a run stops after MAX_CALLS tool calls."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
HARNESS_DIR = ROOT / "harness"
sys.path.insert(0, str(HARNESS_DIR))  # harness.py imports its siblings (sources, report)
spec = importlib.util.spec_from_file_location("harness_main", HARNESS_DIR / "harness.py")
assert spec and spec.loader
harness = importlib.util.module_from_spec(spec)
sys.modules["harness_main"] = harness
spec.loader.exec_module(harness)


class FakeClient:
    """Always asks for one more tool call, like a model that will never answer."""

    def __init__(self):
        self.turns = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.turns += 1
        call = SimpleNamespace(id=f"c{self.turns}", function=SimpleNamespace(name="run_python", arguments='{"code": "1"}'))
        msg = SimpleNamespace(content=None, reasoning_content="", tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_tool_calls_stop_at_the_cap():
    client = FakeClient()
    harness.client = client
    assert harness.chat([]) == "(max tool turns reached)"
    assert client.turns == harness.MAX_CALLS == 10
