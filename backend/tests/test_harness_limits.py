"""The tool-call cap of the analyst loop: at most MAX_TOOL_CALLS calls run per question, even inside a single turn."""

import pytest

pytest.importorskip("openai")  # the `harness` dependency group

from harness import agent  # noqa: E402

from .test_harness_agent import FakeClient, reply, tool_call  # noqa: E402


def run_chat(script):
    lines: list[str] = []
    client = FakeClient(script)
    answer = agent.chat(client, "stand-in", [], lines.append)
    return answer, lines, client


def test_calls_stop_at_the_cap_when_every_turn_asks_for_one(monkeypatch):
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: "ok")
    answer, lines, client = run_chat([reply(tool_calls=[tool_call("run_python", '{"code": "1"}')])] * 20)
    assert answer == "(max tool turns reached)"
    assert len(client.requests) == agent.MAX_TOOL_CALLS == 10


def test_one_turn_cannot_run_more_calls_than_the_budget(monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: ran.append(name) or "ok")
    greedy = [tool_call("run_python", '{"code": "1"}', call_id=f"c{i}") for i in range(agent.MAX_TOOL_CALLS + 5)]
    answer, lines, client = run_chat([reply(tool_calls=greedy)])
    assert len(ran) == agent.MAX_TOOL_CALLS  # the other five were refused, not run
    assert answer == "(max tool turns reached)"
    assert lines[-1] == "[stop] tool call budget used up"
    assert len(client.requests) == 1  # no further turn after the budget is gone


def test_refused_calls_still_get_an_answer_for_their_call_id(monkeypatch):
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: "ok")
    calls = [tool_call("run_python", '{"code": "1"}', call_id=f"c{i}") for i in range(agent.MAX_TOOL_CALLS + 2)]
    messages: list = []
    agent_lines: list[str] = []
    executed = agent._run_tool_calls(reply(tool_calls=calls).choices[0].message, messages, agent_lines.append, 3)
    assert executed == 3
    answered = [m["tool_call_id"] for m in messages if isinstance(m, dict)]
    assert answered == [call.id for call in calls]  # every call id has a result, or the model API rejects the request
    assert agent.TOOL_BUDGET_USED_UP in messages[-1]["content"]


def test_the_budget_is_shared_across_turns(monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(agent, "call_tool", lambda name, arguments: ran.append(name) or "ok")
    four = [tool_call("get_data", "{}", call_id=f"a{i}") for i in range(4)]
    seven = [tool_call("get_data", "{}", call_id=f"b{i}") for i in range(7)]
    answer, lines, client = run_chat([reply(tool_calls=four), reply(tool_calls=seven)])
    assert len(ran) == 10 and len(client.requests) == 2
