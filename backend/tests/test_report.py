"""Tests for harness/report.py: the answer's table goes to prediction.csv and prediction.md."""

import json
import logging

from harness import report

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


def test_a_table_with_other_columns_is_still_written(tmp_path):
    """Small models drop or reorder columns; the files must still appear (a mismatch used to write nothing)."""
    answer = "Prose.\n\n```csv\ntime,metric,value\n2026-11-07T18:00:00Z,imbalance_price,95.4\n```\n"
    csv_path, md_path = report.write_reports(answer, tmp_path)
    assert csv_path.read_text().splitlines() == ["time,metric,value", "2026-11-07T18:00:00Z,imbalance_price,95.4"]
    assert "| time |" in md_path.read_text()


def test_an_answer_without_a_table_still_writes_both_files(tmp_path):
    csv_path, md_path = report.write_reports("No table here.", tmp_path)
    assert csv_path.read_text().strip() == HEADER
    assert md_path.read_text() == "No table here."


def test_reasoning_is_remembered_only_for_rows_that_moved_over_3pct(tmp_path):
    """memory.json: one entry per row that moved more than 3% against the previous run, with the answer's prose."""
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


def test_an_empty_code_fence_does_not_crash_the_report(tmp_path):
    """An answer with an empty ``` block used to raise IndexError and write no files at all."""
    csv_path, md_path = report.write_reports("Before.\n```\n```\nAfter.", tmp_path)
    assert csv_path.read_text().strip() == HEADER and md_path.read_text().startswith("Before.")
    csv_path, _ = report.write_reports("Odd.\n```python\n\n```\n", tmp_path)
    assert csv_path.exists()


def test_a_fence_that_is_not_a_table_is_left_alone(tmp_path):
    answer = "Code:\n```python\nprint(1)\n```\n"
    _, md_path = report.write_reports(answer, tmp_path)
    assert md_path.read_text() == answer


def test_a_second_table_with_other_columns_does_not_mix_rows(tmp_path):
    answer = f"```csv\n{HEADER}\n{ROWS}\n```\n```csv\ntime,value\n2026-11-07T18:00:00Z,1\n```\n"
    csv_path, _ = report.write_reports(answer, tmp_path)
    assert len(csv_path.read_text().splitlines()) == 3


def test_memory_is_capped_and_a_damaged_file_is_replaced_with_a_warning(tmp_path, caplog):
    memory_file = tmp_path / "memory.json"
    memory_file.write_text("{ this is not json")
    previous = [list(report.COLS), *[row.split(",") for row in ROWS.splitlines()]]
    moved = [row.split(",") for row in ROWS.replace("95.4", "120.0").splitlines()]
    with caplog.at_level(logging.WARNING):
        report.remember(moved, "why", previous, tmp_path)
    assert "memory.json unreadable" in caplog.text and len(json.loads(memory_file.read_text())) == 1
    memory_file.write_text(json.dumps([{"n": n} for n in range(500)]))
    report.remember(moved, "why", previous, tmp_path)
    kept = json.loads(memory_file.read_text())
    assert len(kept) == report.MAX_MEMORY_EVENTS and kept[-1]["reasoning"] == "why"


def test_the_command_line_writes_the_files(tmp_path, capsys):
    answer = tmp_path / "answer.txt"
    answer.write_text(f"Prose\n```csv\n{HEADER}\n{ROWS}\n```\n")
    report.main([str(answer), str(tmp_path / "out")])
    assert (tmp_path / "out" / "prediction.csv").exists() and "wrote" in capsys.readouterr().out
