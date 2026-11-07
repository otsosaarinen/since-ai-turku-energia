"""
report.py — export a harness prediction answer to prediction.csv + prediction.md.
Usage: python harness.py -q "predict the next 24 h" > answer.txt
       python report.py answer.txt [outdir]      (also reads stdin if no file)
The harness prompt fixes the columns: horizon,time,area,metric,value,unit,low,high,confidence,drivers
"""

import csv
import io
import json
import pathlib
import re
import sys
from datetime import UTC, datetime

COLS = (
    "horizon",
    "time",
    "area",
    "metric",
    "value",
    "unit",
    "low",
    "high",
    "confidence",
    "drivers",
)
CHANGE = 0.03  # a row is kept in memory when its value moves more than this against the previous run
MEMORY = "memory.json"


def _table(rows):
    """One csv row list → a markdown table."""
    line = lambda r: "| " + " | ".join(c.strip() for c in r) + " |"
    return "\n".join(
        [line(rows[0]), "|" + "---|" * len(rows[0])] + [line(r) for r in rows[1:]]
    )


def _find_tables(answer: str):
    """Return (csv text, original text) for a ```csv block, another fenced table, or a plain table."""
    found = [(m.group(1), m.group(0)) for m in re.finditer(r"```csv[ \t]*\n(.*?)```", answer, re.DOTALL)]
    if not found:
        for m in re.finditer(r"```[a-z]*[ \t]*\n(.*?)```", answer, re.DOTALL):
            first = m.group(1).strip().splitlines()[0].lower()
            if "time" in first and "value" in first:
                found.append((m.group(1), m.group(0)))
    if not found:
        lines = answer.splitlines()
        for i, line in enumerate(lines):
            low = line.strip().lower()
            if low.startswith("horizon,") and "time" in low and "value" in low:
                j = i + 1
                while j < len(lines) and lines[j].strip() and "," in lines[j]:
                    j += 1
                start = i - 1 if i and lines[i - 1].strip().startswith("```") else i
                found.append(("\n".join(lines[i:j]), "\n".join(lines[start:j])))
    return found


def _values(rows):
    """{(time, metric): value} from csv rows; rows that are not data (the header, text) are skipped."""
    t, m, v = COLS.index("time"), COLS.index("metric"), COLS.index("value")
    out = {}
    for r in rows:
        try:
            out[(r[t].strip(), r[m].strip())] = float(r[v])
        except (IndexError, ValueError):
            pass
    return out


def remember(rows, reasoning, previous, outdir, now=None):
    """Append the reasoning behind every row that moved > CHANGE against the previous run to memory.json.

    A store for the website's server side to show why a forecast changed; nothing here displays it.
    The reasoning is the answer's prose (the words around the table), kept to one entry per changed row.
    """
    old = _values(previous)
    events = []
    for (key, value) in _values(rows).items():
        before = old.get(key)
        if not before or abs(value - before) / abs(before) <= CHANGE:
            continue
        events.append(
            {
                "at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
                "time": key[0],
                "metric": key[1],
                "previous": before,
                "value": value,
                "change_pct": round((value - before) / abs(before) * 100, 1),
                "reasoning": reasoning[:1500],
            }
        )
    if not events:
        return None
    path = pathlib.Path(outdir) / MEMORY
    try:
        memory = json.loads(path.read_text())
    except (OSError, ValueError):
        memory = []
    path.write_text(json.dumps(memory[-199:] + events, indent=1))
    return path


def write_reports(answer: str, outdir="reports"):
    """Extract the csv block(s), fenced or plain → prediction.csv and prediction.md. Returns (csv, md)."""
    blocks = list(_find_tables(answer))
    rows, md = [], answer
    for b, original in blocks:
        r = [
            x
            for x in csv.reader(io.StringIO(b.strip()))
            if x and any(c.strip() for c in x)
        ]
        if r and [c.strip().lower() for c in r[0]] != list(COLS):
            raise ValueError(f"csv block header {r[0]} != {list(COLS)}")
        rows += r[1:]  # validated header, append the data rows
        md = md.replace(original, _table(r))
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    was = (out / "prediction.csv").read_text() if (out / "prediction.csv").exists() else ""
    with (out / "prediction.csv").open("w", newline="") as f:
        csv.writer(f).writerows([list(COLS)] + rows)
    (out / "prediction.md").write_text(md)
    prose = answer
    for _, original in blocks:
        prose = prose.replace(original, "")
    remember(rows, prose.strip(), list(csv.reader(io.StringIO(was))), out)
    return out / "prediction.csv", out / "prediction.md"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    answer = pathlib.Path(args[0]).read_text() if args else sys.stdin.read()
    c, m = write_reports(answer, args[1] if len(args) > 1 else "reports")
    print(f"wrote {c} and {m}")
