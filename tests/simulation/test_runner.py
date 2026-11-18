import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from uav_onboard_planner.simulation.config import load_config
from uav_onboard_planner.simulation.runner import create_episode, run


@pytest.mark.integration
def test_run_records_both_aircraft_and_configuration(tmp_path: Path) -> None:
    config = replace(
        load_config(Path("configs/simulation/scenarios/default.yaml")), duration=0.05
    )
    output = tmp_path / "run"
    statuses = run(config, output)
    assert not (output / "altitude.csv").exists()
    with (output / "trajectory.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert {row["drone"] for row in rows} == {"survey", "traffic"}
    assert max(float(row["time_s"]) for row in rows) == pytest.approx(0.05)
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["configuration"]["seed"] == 42
    assert "mission_cancellations" not in metadata["configuration"]
    assert all(
        "altimeter" not in drone for drone in metadata["configuration"]["drones"]
    )
    assert metadata["packages"]["rotorpy"]
    assert metadata["missions"] == statuses
    assert metadata["status"] == "finished"
    assert metadata["end_reason"] == "time_limit"
    with pytest.raises(FileExistsError):
        run(config, output)


@pytest.mark.integration
@pytest.mark.parametrize("duration", [0.07, 0.1, 0.3])
def test_final_sample_is_not_duplicated_by_rounding(
    tmp_path: Path, duration: float
) -> None:
    config = replace(
        load_config(Path("configs/simulation/scenarios/default.yaml")),
        duration=duration,
        sample_interval=duration,
    )
    output = tmp_path / "run"
    run(config, output)
    with (output / "trajectory.csv").open() as stream:
        rows = [row for row in csv.DictReader(stream) if row["drone"] == "survey"]
    assert len(rows) == 2
    assert float(rows[-1]["time_s"]) == pytest.approx(config.duration)


@pytest.mark.integration
def test_scheduled_route_matches_recording(tmp_path: Path) -> None:
    config = load_config(Path("configs/simulation/scenarios/route_change.yaml"))
    output = tmp_path / "run"
    assert run(config, output) == {"survey": "completed"}
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["configuration"]["drones"][0]["altimeter"] == {
        "noise_std_m": 0.2,
        "delay_s": 0.025,
    }
    with (output / "trajectory.csv").open() as stream:
        rows = list(csv.DictReader(stream))

    episode = create_episode(config)
    assert episode.altitude_observations() == {"survey": None}
    sample = episode.snapshot()["survey"]
    for row in rows:
        time = float(row["time_s"])
        while sample.state.time < time - 1e-10:
            sample = episode.step()["survey"]
        assert sample.state.time == pytest.approx(time)
        assert sample.state.position == pytest.approx(
            tuple(float(row[key]) for key in ("east_m", "north_m", "up_m"))
        )
        assert sample.status == row["status"]
    assert sample.state.position == pytest.approx((2, 4, 10), abs=0.3)
    altitude = episode.altitude_observations()["survey"]
    assert altitude is not None
    assert altitude.measured_at_s < altitude.available_at_s <= episode.time

    with (output / "altitude.csv").open() as stream:
        measurements = list(csv.DictReader(stream))
    assert {row["drone"] for row in measurements} == {"survey"}
    assert len(measurements) > len(rows)
    assert float(measurements[0]["measured_at_s"]) == 0
    assert float(measurements[0]["received_at_s"]) == pytest.approx(0.03)
    assert float(measurements[-1]["altitude_m"]) == altitude.altitude_m
    times = [float(row["measured_at_s"]) for row in measurements]
    assert times == sorted(set(times))
    for time, row in zip(times, measurements, strict=True):
        available = float(row["available_at_s"])
        received = float(row["received_at_s"])
        assert available == pytest.approx(time + 0.025)
        assert available <= received <= episode.time


@pytest.mark.integration
def test_cancellation_scenario_records_the_remaining_flight(tmp_path: Path) -> None:
    config = load_config(Path("configs/simulation/scenarios/mission_cancellation.yaml"))
    output = tmp_path / "run"
    assert run(config, output) == {"survey": "cancelled", "traffic": "active"}
    with (output / "trajectory.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    first_cancelled = next(row for row in rows if row["status"] == "cancelled")
    assert first_cancelled["drone"] == "survey"
    assert float(first_cancelled["time_s"]) == pytest.approx(2.6, abs=config.time_step)
    traffic = [row for row in rows if row["drone"] == "traffic"]
    assert all(row["status"] == "active" for row in traffic)
    assert float(traffic[-1]["time_s"]) == pytest.approx(config.duration)
    assert float(traffic[-1]["north_m"]) > float(traffic[0]["north_m"])
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["configuration"]["mission_cancellations"] == [
        {"time": 2.505, "drone": "survey"}
    ]
    assert metadata["configuration"]["drones"][0]["altimeter"]["outages"] == [
        {"start_s": 1.25, "end_s": 2.0}
    ]
    with (output / "altitude.csv").open() as stream:
        received = [float(row["received_at_s"]) for row in csv.DictReader(stream)]
    assert received[0] < 1.25
    assert received[-1] > 2.025
    assert all(not 1.25 <= time < 2.025 for time in received)
