from pathlib import Path

import pytest
import yaml

from uav_onboard_planner.simulation.config import load_config


def test_example_contains_both_aircraft_types() -> None:
    config = load_config(Path("scenarios/simulation/default.yaml"))
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
        ("duration", 10**400),
        ("seed", True),
        ("show_animation", "false"),
        ("sample_interval", 0.001),
    ],
)
def test_invalid_run_parameters(tmp_path: Path, field: str, value) -> None:
    data = yaml.safe_load(Path("scenarios/simulation/default.yaml").read_text())
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
        ("heading", "north"),
        ("waypoints", []),
        ("arrival_radius", 0),
        ("altimeter", None),
        ("altimeter", {"noise_std_m": 0.2}),
        ("altimeter", {"noise_std_m": -0.2, "delay_s": 0}),
        ("altimeter", {"noise_std_m": 0.2, "delay_s": True}),
        (
            "altimeter",
            {"noise_std_m": 0, "delay_s": 0, "outages": [{"start_s": 2, "end_s": 1}]},
        ),
        (
            "altimeter",
            {
                "noise_std_m": 0,
                "delay_s": 0,
                "outages": [{"start_s": 1, "end_s": 3}, {"start_s": 2, "end_s": 4}],
            },
        ),
    ],
)
def test_invalid_aircraft_parameters(tmp_path: Path, field: str, value) -> None:
    data = yaml.safe_load(Path("scenarios/simulation/default.yaml").read_text())
    data["drones"][0][field] = value
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("scenarios/simulation/default.yaml").read_text())
    data["drones"][1]["name"] = data["drones"][0]["name"]
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="unique"):
        load_config(path)


def test_altimeter_profile_is_resolved_relative_to_the_scenario(tmp_path: Path) -> None:
    profiles = tmp_path / "sensors"
    profiles.mkdir()
    profile = profiles / "altimeter.yaml"
    profile.write_text("noise_std_m: 0.3\ndelay_s: 0.05\n")
    data = yaml.safe_load(Path("scenarios/simulation/default.yaml").read_text())
    data["drones"][0]["altimeter"] = "sensors/altimeter.yaml"
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(yaml.safe_dump(data))

    altimeter = load_config(scenario).drones[0].altimeter
    assert altimeter is not None
    assert altimeter.noise_std_m == 0.3
    assert altimeter.delay_s == 0.05

    profile.write_text("noise_std_m: 0.3\ndelay_s: -1\n")
    with pytest.raises(ValueError, match="delay_s"):
        load_config(scenario)

    profile.unlink()
    with pytest.raises(FileNotFoundError) as error:
        load_config(scenario)
    assert error.value.filename == str(profile)


@pytest.mark.parametrize(
    "cancellation,message",
    [
        ({"time": 60, "drone": "survey"}, "before episode end"),
        ({"time": 1, "drone": "missing"}, "unknown drone"),
        ({"time": 1, "drone": "survey"}, "conflicting mission events"),
    ],
)
def test_invalid_mission_cancellation(
    tmp_path: Path, cancellation, message: str
) -> None:
    data = yaml.safe_load(Path("scenarios/simulation/default.yaml").read_text())
    data["mission_cancellations"] = [cancellation]
    data["route_changes"] = [
        {"time": 1, "drone": "survey", "arrival_radius": 1, "waypoints": [[1, 0, 10]]}
    ]
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match=message):
        load_config(path)
