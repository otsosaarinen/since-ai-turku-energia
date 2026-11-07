"""Write submissions and run the organiser's validator / scorer (starter_package_v1 stays read-only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "starter_package_v1"  # organiser tools, read-only reference
SPIKE_MARGIN_EUR = 50  # organiser definition of an exceptional price: spot +- 50 EUR/MWh
SUBMISSION_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def write_submission(df: pd.DataFrame, path: Path, template: Path) -> None:
    """Write the forecast in the organisers' exact column order and number/time formats."""
    columns = pd.read_csv(template, nrows=0).columns.tolist()
    out = df.copy()
    for col in ("forecast_origin_utc", "delivery_start_utc", "data_cutoff_utc"):
        out[col] = pd.to_datetime(out[col], utc=True).dt.strftime(SUBMISSION_TIME_FORMAT)
    path.parent.mkdir(parents=True, exist_ok=True)
    out[columns].to_csv(path, index=False, float_format="%.6f", lineterminator="\n", encoding="utf-8")


def _run(script: str, *args: str) -> tuple[int, str]:
    """Run an organiser script in isolated mode and return (exit code, stdout + stderr)."""
    result = subprocess.run([sys.executable, "-I", str(PKG / script), *args], capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def validate(backtest: Path, origins: Path) -> tuple[int, str]:
    """Run the organiser's submission validator."""
    return _run("validate_submission.py", "--backtest", str(backtest), "--origins", str(origins))


def score(submission: Path, actuals: Path, out_dir: Path, baseline_summary: Path | None = None) -> tuple[int, str]:
    """Run the organiser's scorer (optionally against the baseline's summary)."""
    args = [
        "--submission",
        str(submission),
        "--actuals",
        str(actuals),
        "--spike-margin",
        str(SPIKE_MARGIN_EUR),
        "--output-dir",
        str(out_dir),
    ]
    if baseline_summary is not None:
        args += ["--baseline-summary", str(baseline_summary)]
    return _run("score.py", *args)
