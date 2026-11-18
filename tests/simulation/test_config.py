from pathlib import Path

import pytest
import yaml

from uav_onboard_planner.simulation.config import load_config


def test_load_config_accepts_both_aircraft_types(simulation_config_path: Path) -> None:
    config = load_config(simulation_config_path)
    assert {drone.backend for drone in config.drones} == {"rotorpy", "jsbsim"}
    assert len({drone.name for drone in config.drones}) == len(config.drones)


@pytest.mark.parametrize(
    "content", ["[]", "backend: unknown", "!!python/object:os.system {}"]
)
def test_malformed_configuration_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "scenario.yaml"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("time_step", 0),
        ("time_step", 0.1),
        ("duration", float("nan")),
        ("seed", True),
        ("show_animation", "false"),
        ("sample_interval", 0.001),
    ],
)
def test_invalid_run_parameters(
    tmp_path: Path, simulation_config_path: Path, field: str, value
) -> None:
    data = yaml.safe_load(simulation_config_path.read_text())
    data[field] = value
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", ""),
        ("backend", "unknown"),
        ("model", "unknown"),
        ("position", [0, 0]),
        ("position", [0, 0, -1]),
        ("speed", -1),
        ("heading", float("inf")),
        ("waypoints", []),
        ("arrival_radius", 0),
    ],
)
def test_invalid_aircraft_parameters(
    tmp_path: Path, simulation_config_path: Path, field: str, value
) -> None:
    data = yaml.safe_load(simulation_config_path.read_text())
    data["drones"][0][field] = value
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)


def test_duplicate_names_are_rejected(
    tmp_path: Path, simulation_config_path: Path
) -> None:
    data = yaml.safe_load(simulation_config_path.read_text())
    data["drones"][1]["name"] = data["drones"][0]["name"]
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="unique"):
        load_config(path)
