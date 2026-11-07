"""Tests for harness/report.py: the answer's table goes to prediction.csv and prediction.md."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harness_report", ROOT / "harness" / "report.py")
assert spec and spec.loader
report = importlib.util.module_from_spec(spec)
sys.modules["harness_report"] = report
spec.loader.exec_module(report)

HEADER = "horizon,time,area,metric,value,unit,low,high,confidence,drivers"
ROWS = (
    "24h,2026-11-07T18:00:00Z,FI,spot_price,95.4,EUR/MWh,80.1,112.0,0.7,x\n"
    "24h,2026-11-07T20:00:00Z,FI,spot_price,110.2,EUR/MWh,92.0,130.0,0.6,x"
)


def test_fenced_csv_is_written(tmp_path):
    answer = f"Prose.\n\n```csv\n{HEADER}\n{ROWS}\n```\n"
    csv_path, md_path = report.write_reports(answer, tmp_path)
    assert len(csv_path.read_text().splitlines()) == 3
    assert "| horizon |" in md_path.read_text()


def test_plain_table_without_a_fence_is_written(tmp_path):
    answer = f"Prose.\n\n{HEADER}\n{ROWS}\n"
    csv_path, md_path = report.write_reports(answer, tmp_path)
    assert len(csv_path.read_text().splitlines()) == 3
    assert "```" not in md_path.read_text()


def test_reasoning_is_remembered_only_for_rows_that_moved_over_3pct(tmp_path):
    """memory.json: one entry per row that moved more than 3% against the previous run, with the answer's prose."""
    import json

    report.write_reports(f"First reason.\n\n```csv\n{HEADER}\n{ROWS}\n```\n", tmp_path)
    assert not (tmp_path / "memory.json").exists()  # nothing to compare against yet

    small = ROWS.replace("95.4", "96.0")  # +0.6%
    report.write_reports(f"Small move.\n\n```csv\n{HEADER}\n{small}\n```\n", tmp_path)
    assert not (tmp_path / "memory.json").exists()

    moved = ROWS.replace("95.4", "99.0")  # +3.8%
    report.write_reports(f"Spot rose.\n\n```csv\n{HEADER}\n{moved}\n```\n", tmp_path)
    memory = json.loads((tmp_path / "memory.json").read_text())
    assert len(memory) == 1
    assert memory[0]["time"] == "2026-11-07T18:00:00Z" and memory[0]["metric"] == "spot_price"
    assert memory[0]["previous"] == 96.0 and memory[0]["value"] == 99.0 and memory[0]["change_pct"] == 3.1
    assert memory[0]["reasoning"] == "Spot rose."
    assert "horizon" not in memory[0]["reasoning"]  # the table is not part of the reasoning
