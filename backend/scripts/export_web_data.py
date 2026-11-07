"""Convert forecast CSVs to compact JSON for the web viewer (frontend/). No spot prices are exported.

usage: uv run scripts/export_web_data.py
"""

from __future__ import annotations

import json

import pandas as pd

from src.alerts import generate_situational_overview
from src.exports import web_payload
from src.train import ROOT  # backend/: data, outputs and configs live below it

REPO_ROOT = ROOT.parent  # holds backend/ and frontend/
OUT = REPO_ROOT / "frontend" / "public" / "data"
SOURCES = (
    ("validation", "outputs/validation/backtest_vs_actual.csv"),
    ("final", "outputs/final/forecast_backtest.csv"),
)


def main() -> None:
    """Write validation.json / final.json and the operational alert files for every forecast that exists."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, relative_path in SOURCES:
        source = ROOT / relative_path
        if not source.exists():
            continue
        df = pd.read_csv(source)
        payload = web_payload(df, name)
        target = OUT / f"{name}.json"
        target.write_text(json.dumps(payload, separators=(",", ":")))
        print(name, len(payload["rows"]), "rows,", round(target.stat().st_size / 1e6, 1), "MB")

        # Level 2 operational situational alerts for shift supervisors
        alerts = generate_situational_overview(df)
        alerts_file = OUT / f"alerts_{name}.json"
        alerts_file.write_text(json.dumps(alerts, indent=2))
        print(f"  -> {len(alerts)} operational alerts exported to {alerts_file.name}")


if __name__ == "__main__":
    main()
