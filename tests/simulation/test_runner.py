import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from uav_onboard_planner.simulation.config import load_config
from uav_onboard_planner.simulation.runner import run


@pytest.mark.integration
def test_run_records_both_aircraft_and_configuration(tmp_path: Path) -> None:
    config = replace(load_config(Path("configs/simulation/default.yaml")), duration=0.05)
    output = tmp_path / "run"
    statuses = run(config, output)
    with (output / "trajectory.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert {row["drone"] for row in rows} == {"survey", "traffic"}
    assert max(float(row["time_s"]) for row in rows) == pytest.approx(0.05)
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["configuration"]["seed"] == 42
    assert metadata["packages"]["rotorpy"]
    assert metadata["missions"] == statuses
    assert metadata["status"] == "finished"
    with pytest.raises(FileExistsError):
        run(config, output)


@pytest.mark.integration
@pytest.mark.parametrize("duration", [0.07, 0.1, 0.3])
def test_final_sample_is_not_duplicated_by_rounding(tmp_path: Path, duration: float) -> None:
    config = replace(load_config(Path("configs/simulation/default.yaml")), duration=duration, sample_interval=duration)
    output = tmp_path / "run"
    run(config, output)
    with (output / "trajectory.csv").open() as stream:
        rows = [row for row in csv.DictReader(stream) if row["drone"] == "survey"]
    assert len(rows) == 2
    assert float(rows[-1]["time_s"]) == pytest.approx(config.duration)
