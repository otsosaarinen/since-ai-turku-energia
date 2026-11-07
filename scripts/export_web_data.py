"""Convert forecast CSVs to compact JSON for the React viewer (web/). No spot prices are exported.
usage: uv run scripts/export_web_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.exports import web_payload  # noqa: E402
from src.alerts import generate_situational_overview  # noqa: E402

OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

for name, src in (("validation", "outputs/validation/backtest_vs_actual.csv"), ("final", "outputs/final/forecast_backtest.csv")):
    src_path = ROOT / src
    if src_path.exists():
        df = pd.read_csv(src_path)
        payload = web_payload(df, name)
        (OUT / f"{name}.json").write_text(json.dumps(payload, separators=(",", ":")))
        print(name, len(payload["rows"]), "rows,", round((OUT / f"{name}.json").stat().st_size / 1e6, 1), "MB")

        # Export Level 2 operational situational alerts for shift supervisors
        alerts = generate_situational_overview(df)
        alerts_file = OUT / f"alerts_{name}.json"
        alerts_file.write_text(json.dumps(alerts, indent=2))
        print(f"  -> {len(alerts)} operational alerts exported to {alerts_file.name}")
