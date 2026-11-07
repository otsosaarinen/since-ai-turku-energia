"""The model's tools: argument handling, saving fetched data to files, and that bad model output cannot escape."""

import pytest

from harness import tools


def test_a_fetched_result_is_saved_to_a_file_and_the_model_gets_a_preview(tmp_path):
    text = '{"data": [' + ", ".join(str(n) for n in range(2000)) + "]}"
    reply = tools.save_result(text, "fingrid_wind_gen", tmp_path)
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and files[0].read_text() == text and files[0].suffix == ".json"
    assert str(files[0]) in reply and "more characters" in reply and "json.load(open(" in reply
    assert len(reply) < tools.PREVIEW_CHARS + 500


def test_non_json_results_get_a_txt_file_and_a_matching_hint(tmp_path):
    reply = tools.save_result("time,value\n1,2\n", "fetch_url", tmp_path)
    (saved,) = tmp_path.iterdir()
    assert saved.suffix == ".txt" and ".read()" in reply and "json.load" not in reply


def test_errors_are_passed_through_unsaved(tmp_path):
    assert tools.save_result("Error: boom", "x", tmp_path) == "Error: boom"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "name",
    ["../../etc/passwd", "..\\..\\x", "a/b/c", "/abs/path", "x\0y", "name with spaces and $(rm -rf ~)", "", 12345],
)
def test_a_hostile_file_name_cannot_leave_the_data_folder(tmp_path, name):
    data_dir = tmp_path / "data"
    tools.save_result('{"a": 1}', name, data_dir)
    (saved,) = data_dir.iterdir()
    assert saved.parent == data_dir and "/" not in saved.name and "\\" not in saved.name and ".." not in saved.name
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == [saved]  # nothing was written anywhere else


def test_call_tool_never_raises_and_turns_bad_calls_into_text():
    assert tools.call_tool("nope", {}).startswith("Error: unknown tool nope")
    for bad_arguments in (None, [], "text", 5, ["code"]):
        assert tools.call_tool("run_python", bad_arguments).startswith("Error:")
    assert "'code' is required" in tools.call_tool("run_python", {})
    assert "'code' is required" in tools.call_tool("run_python", {"code": 7})
    assert "'url' is required" in tools.call_tool("fetch_url", {})
    assert "'source' is required" in tools.call_tool("get_data", {"params": {}})
    assert "'params' must be an object" in tools.call_tool("get_data", {"source": "nordpool_price", "params": [1]})


def test_call_tool_survives_a_crashing_handler(monkeypatch):
    def broken(arguments: dict) -> str:
        raise RuntimeError("boom with secret-ish text")

    monkeypatch.setitem(tools.HANDLERS, "run_python", broken)
    assert tools.call_tool("run_python", {"code": "x"}) == "Error: run_python failed: boom with secret-ish text"


def test_tool_results_never_contain_a_key_value(monkeypatch):
    monkeypatch.setenv("FINGRID_API_KEY", "fake-fingrid-key-0001")
    monkeypatch.setitem(tools.HANDLERS, "run_python", lambda arguments: "the key is fake-fingrid-key-0001")
    assert "fake-fingrid-key-0001" not in tools.call_tool("run_python", {"code": "x"})


def test_get_data_goes_through_save_result(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(
        tools, "get_data", lambda source, params: seen.update(source=source, params=params) or '{"ok": true}'
    )
    monkeypatch.setattr(tools, "FETCHED_DATA_DIR", tmp_path)
    monkeypatch.setattr(tools, "save_result", lambda text, name, data_dir=tmp_path: f"saved {name}: {text}")
    assert tools.call_tool("get_data", {"source": "spot_price_fi"}) == 'saved spot_price_fi: {"ok": true}'
    assert seen == {"source": "spot_price_fi", "params": {}}


def test_tool_schemas_match_the_handlers():
    names = [tool["function"]["name"] for tool in tools.TOOLS]
    assert names == ["run_python", "fetch_url", "get_data"] and set(names) == set(tools.HANDLERS)
    get_data = tools.TOOLS[2]["function"]["parameters"]
    assert "fingrid_imbalance_price" in get_data["properties"]["source"]["enum"] and get_data["required"] == ["source"]
