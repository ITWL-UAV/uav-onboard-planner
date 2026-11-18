from pathlib import Path

import pytest


@pytest.fixture
def simulation_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "simulation.yaml"
