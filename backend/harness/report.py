"""Turn a harness answer into files: its csv table -> prediction.csv + prediction.md, and a memory of big changes.

    uv run python -m harness.report answer.txt [outdir]      (reads stdin when no file is given)

The prompt fixes the columns (COLS) but small models vary, so the model's own header is kept. memory.json keeps the
answer's reasoning for every row that moved more than 3 % against the previous run (a store for the server side;
nothing displays it yet).
"""

import argparse
import csv
import io
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from .paths import REPORTS_DIR

logger = logging.getLogger(__name__)

COLS = ("horizon", "time", "area", "metric", "value", "unit", "low", "high", "confidence", "drivers")
CHANGE = 0.03  # a row is remembered when its value moves more than this against the previous run
MEMORY_FILE = "memory.json"
MAX_MEMORY_EVENTS = 200
MAX_REASONING_CHARS = 1500
CSV_FENCE = re.compile(r"```csv[ \t]*\n(.*?)```", re.DOTALL)
ANY_FENCE = re.compile(r"```[a-z]*[ \t]*\n(.*?)```", re.DOTALL)
Rows = list[list[str]]


def _markdown_table(rows: Rows) -> str:
    """csv rows (header first) -> a markdown table."""

    def line(row: list[str]) -> str:
        return "| " + " | ".join(cell.strip() for cell in row) + " |"

    return "\n".join([line(rows[0]), "|" + "---|" * len(rows[0]), *(line(row) for row in rows[1:])])


def _looks_like_table_header(text: str) -> bool:
    first_line = text.strip().splitlines()[0].lower() if text.strip() else ""  # an empty fence has no first line
    return "time" in first_line and "value" in first_line


def _find_plain_tables(answer: str) -> list[tuple[str, str]]:
    """Tables written without a fence: a `horizon,...` header line followed by comma lines."""
    lines = answer.splitlines()
    found = []
    for index, line in enumerate(lines):
        lowered = line.strip().lower()
        if lowered.startswith("horizon,") and "time" in lowered and "value" in lowered:
            end = index + 1
            while end < len(lines) and lines[end].strip() and "," in lines[end]:
                end += 1
            start = index - 1 if index and lines[index - 1].strip().startswith("```") else index
            found.append(("\n".join(lines[index:end]), "\n".join(lines[start:end])))
    return found


def _find_tables(answer: str) -> list[tuple[str, str]]:
    """(csv text, original text) for each ```csv block, else another fenced table, else a plain table."""
    found = [(match.group(1), match.group(0)) for match in CSV_FENCE.finditer(answer)]
    if not found:
        found = [(m.group(1), m.group(0)) for m in ANY_FENCE.finditer(answer) if _looks_like_table_header(m.group(1))]
    return found or _find_plain_tables(answer)


def _values(rows: Rows, header: list[str] | tuple[str, ...] = COLS) -> dict[tuple[str, str], float]:
    """{(time, metric): value} from csv rows; rows that are not data (the header, text) are skipped."""
    try:
        time_col, metric_col, value_col = header.index("time"), header.index("metric"), header.index("value")
    except ValueError:  # the model's table has no time/metric/value column: nothing to compare
        return {}
    values = {}
    for row in rows:
        try:
            values[(row[time_col].strip(), row[metric_col].strip())] = float(row[value_col])
        except (IndexError, ValueError):
            continue  # a short row or a non-number is not data
    return values


def _load_memory(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        logger.warning("memory.json unreadable, starting a new one: %s", error)
        return []


def remember(
    rows: Rows,
    reasoning: str,
    previous: Rows,
    outdir: Path,
    now: datetime | None = None,
    header: list[str] | tuple[str, ...] = COLS,
) -> Path | None:
    """Append the reasoning behind every row that moved more than CHANGE against the previous run to memory.json."""
    old = _values(previous[1:], previous[0]) if previous else {}
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    events = []
    for (time_text, metric), value in _values(rows, header).items():
        before = old.get((time_text, metric))
        if not before or abs(value - before) / abs(before) <= CHANGE:
            continue
        events.append(
            {
                "at": stamp,
                "time": time_text,
                "metric": metric,
                "previous": before,
                "value": value,
                "change_pct": round((value - before) / abs(before) * 100, 1),
                "reasoning": reasoning[:MAX_REASONING_CHARS],
            }
        )
    if not events:
        return None
    path = Path(outdir) / MEMORY_FILE
    path.write_text(json.dumps((_load_memory(path) + events)[-MAX_MEMORY_EVENTS:], indent=1), encoding="utf-8")
    return path


def _read_csv(text: str) -> Rows:
    return [row for row in csv.reader(io.StringIO(text.strip())) if row and any(cell.strip() for cell in row)]


def write_reports(answer: str, outdir: Path | str = REPORTS_DIR) -> tuple[Path, Path]:
    """Extract the csv block(s), fenced or plain, into prediction.csv and prediction.md. Returns (csv path, md path)."""
    blocks = _find_tables(answer)
    rows: Rows = []
    header: list[str] | None = None
    markdown = answer
    for block, original in blocks:
        table = _read_csv(block)
        if not table:
            continue
        columns = [column.strip() for column in table[0]]
        if header is None:
            header = columns  # the model's own columns; the prompt asks for COLS but small models vary
        if columns != header:
            continue  # a second table with other columns would mix rows
        rows += table[1:]
        markdown = markdown.replace(original, _markdown_table(table))
    header = header or list(COLS)
    folder = Path(outdir)
    folder.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = folder / "prediction.csv", folder / "prediction.md"
    previous = _read_csv(csv_path.read_text(encoding="utf-8")) if csv_path.exists() else []
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([header, *rows])
    md_path.write_text(markdown, encoding="utf-8")
    prose = answer
    for _, original in blocks:
        prose = prose.replace(original, "")
    remember(rows, prose.strip(), previous, folder, header=header)
    return csv_path, md_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m harness.report", description=__doc__.splitlines()[0])
    parser.add_argument("answer", nargs="?", help="file with the answer text (default: stdin)")
    parser.add_argument("outdir", nargs="?", default=str(REPORTS_DIR))
    args = parser.parse_args(argv)
    text = Path(args.answer).read_text(encoding="utf-8") if args.answer else sys.stdin.read()
    csv_path, md_path = write_reports(text, args.outdir)
    print(f"wrote {csv_path} and {md_path}")


if __name__ == "__main__":
    main()
