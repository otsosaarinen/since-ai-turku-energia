from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.availability import AvailabilityIndex, load_all

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg() -> dict:
    """The project config."""
    return yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())


@pytest.fixture(scope="session")
def long_data(cfg: dict) -> pd.DataFrame:
    """Inputs plus spot as one long table (skips the test when data/ is absent)."""
    inp, spot = ROOT / cfg["paths"]["inputs"], ROOT / cfg["paths"]["spot"]
    if not inp.exists():
        pytest.skip("data/ not present (data is not part of the repository)")
    return load_all(inp, spot)


@pytest.fixture(scope="session")
def index(long_data: pd.DataFrame) -> AvailabilityIndex:
    """Availability index over the whole data set."""
    return AvailabilityIndex(long_data)
