from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg():
    return yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())


@pytest.fixture(scope="session")
def long_data(cfg):
    from src.availability import load_all
    inp, spot = ROOT / cfg["paths"]["inputs"], ROOT / cfg["paths"]["spot"]
    if not inp.exists():
        pytest.skip("data/ not present (data is not part of the repository)")
    return load_all(inp, spot)


@pytest.fixture(scope="session")
def index(long_data):
    from src.availability import AvailabilityIndex
    return AvailabilityIndex(long_data)
