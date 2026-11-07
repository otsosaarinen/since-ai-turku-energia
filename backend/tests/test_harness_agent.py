"""The analyst loop with a stand-in model (no network, model server or keys): tool round trips, budgets, progress."""

import json
import re
from types import SimpleNamespace

import pytest

pytest.importorskip("openai")  # the `harness` dependency group

from openai import BadRequestError, InternalServerError  # noqa: E402

from harness import agent  # noqa: E402


def tool_call(name: str, arguments: str, call_id: str = "c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def reply(content=None, tool_calls=None, reasoning=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """Returns the scripted replies one by one; an Exception in the script is raised."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})  # a snapshot: the loop keeps appending
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def http_error(cls):
    """An openai error of the given class without needing the HTTP library behind it (it differs between versions)."""
    error = cls.__new__(cls)
    Exception.__init__(error, "cut off")
    return error


def run(script):
    lines: list[str] = []
    client = FakeClient(script)
    answer = agent.chat(client, "m", [{"role": "system", "content": "s"}], lines.append)
    return answer, lines, client


def test_a_plain_answer_ends_the_run():
    answer, lines, _ = run([reply("hello", reasoning="thinking about it")])
    assert answer == "hello"
    assert lines[0] == "[turn 1/10] asking the model"
    assert lines[1] == "[think] " + json.dumps("thinking about it") and lines[-1] == "[done] final answer received"


def test_a_tool_call_is_run_and_its_result_goes_back_to_the_model(monkeypatch):
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: f"ran {name} {arguments}")
    answer, lines, client = run([reply(tool_calls=[tool_call("run_python", '{"code": "print(1)"}')]), reply("done")])
    assert answer == "done"
    assert lines[1].startswith('[tool] run_python {"code": "print(1)"}')
    assert lines[2].startswith("[result] ") and "characters: " in lines[2] and "ran run_python" in lines[2]
    tool_message = client.requests[1]["messages"][-1]
    assert (
        tool_message["role"] == "tool"
        and tool_message["tool_call_id"] == "c1"
        and "ran run_python" in tool_message["content"]
    )


def test_progress_lines_match_what_the_website_parses(monkeypatch):
    """frontend/src/features/harness/lib/progressSteps.ts matches these line shapes; keep them stable."""
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: "result text")
    _, lines, _ = run([reply(tool_calls=[tool_call("get_data", '{"source": "x"}')], reasoning="r"), reply("done")])
    assert re.match(r"^\[turn \d+/\d+\]", lines[0])
    assert any(re.match(r"^\[tool\] \w+ ?(.*)$", line) for line in lines)
    assert any(re.match(r"^\[result\] (\d+) characters: (.*)$", line) for line in lines)
    assert any(line.startswith("[think] ") for line in lines) and lines[-1].startswith("[done]")


def test_bad_tool_arguments_are_reported_to_the_model_not_raised():
    for arguments in ("{not json", "[1, 2]", '"just text"', "null", "{}"):
        answer, lines, client = run([reply(tool_calls=[tool_call("run_python", arguments)]), reply("recovered")])
        assert answer == "recovered", arguments
        assert client.requests[1]["messages"][-1]["content"].startswith("Error"), arguments


def test_an_unknown_tool_is_reported_to_the_model():
    _, _, client = run([reply(tool_calls=[tool_call("delete_everything", "{}")]), reply("ok")])
    assert "unknown tool delete_everything" in client.requests[1]["messages"][-1]["content"]


def test_a_reply_without_text_gives_an_empty_answer_not_none():
    answer, _, _ = run([reply(None)])
    assert answer == ""


def test_the_tool_turn_budget_stops_an_endless_loop(monkeypatch):
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: "again")
    answer, lines, client = run([reply(tool_calls=[tool_call("run_python", '{"code": "x"}')])] * agent.MAX_TURNS)
    assert answer == "(max tool turns reached)" and lines[-1] == "[stop] tool turn budget used up"
    assert len(client.requests) == agent.MAX_TURNS


def test_cut_off_tool_calls_get_their_own_small_budget():
    broken = http_error(InternalServerError)
    answer, lines, client = run([broken, broken, reply("fine")])
    assert answer == "fine"
    assert sum("broken tool call" in line for line in lines) == 2
    assert [line for line in lines if line.startswith("[turn")] == [
        "[turn 1/10] asking the model"
    ] * 3  # retries reuse the turn
    assert client.requests[-1]["messages"][-1]["content"] == agent.BROKEN_CALL_HINT
    answer, lines, _ = run([http_error(BadRequestError)] * (agent.MAX_BROKEN_CALLS + 1))
    assert "kept sending broken tool calls" in answer and lines[-1].startswith("[stop]")


def test_a_key_for_openrouter_is_never_sent_to_a_local_server(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key-0003")
    client, model = agent.make_client("llamacpp", "some-model")
    assert client.api_key == "llamacpp" and model == "some-model"
    client, _ = agent.make_client("openrouter", "m")
    assert client.api_key == "fake-openrouter-key-0003"
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(SystemExit):
        agent.make_client("openrouter", "m")


def test_command_line_options(monkeypatch):
    monkeypatch.delenv("HARNESS_PROVIDER", raising=False)
    monkeypatch.delenv("HARNESS_PROGRESS", raising=False)
    args = agent.parse_args(["-p", "llamacpp", "-m", "M", "-q", "question", "--progress"])
    assert (args.provider, args.model, args.prompt, args.progress) == ("llamacpp", "M", "question", True)
    assert agent.parse_args([]).provider == "ollama" and not agent.parse_args([]).progress
    with pytest.raises(SystemExit):
        agent.parse_args(["-p", "nonsense"])
    monkeypatch.setenv("HARNESS_PROVIDER", "bogus")
    with pytest.raises(SystemExit):
        agent.parse_args([])


def test_export_writes_the_table_and_a_failure_does_not_lose_the_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "REPORTS_DIR", tmp_path)
    table = (
        "horizon,time,area,metric,value,unit,low,high,confidence,drivers\n24h,2026-11-07T18:00:00Z,FI,x,1,u,0,2,high,d"
    )
    answer = f"Prose\n```csv\n{table}\n```"
    assert agent.export(answer) == answer and (tmp_path / "prediction.csv").exists()
    monkeypatch.setattr(agent, "REPORTS_DIR", tmp_path / "file")
    (tmp_path / "file").write_text("a file, not a folder")
    assert agent.export(answer) == answer  # OSError is logged, the answer survives
