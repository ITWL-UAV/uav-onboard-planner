import csv
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from platform import python_version
from typing import NotRequired, TypedDict

from .config import SimulationConfig
from .contracts import Autopilot
from .episode import Episode, FlightSample
from .mission import Flight, Simulation


class RunMetadata(TypedDict):
    configuration: dict[str, object]
    python: str
    packages: dict[str, str]
    status: str
    missions: NotRequired[dict[str, str]]
    simulated_seconds: NotRequired[float]


def create_simulation(config: SimulationConfig) -> Simulation:
    from .adapters.jsbsim import JSBSimAutopilot
    from .adapters.rotorpy import RotorPyAutopilot

    flights = {}
    autopilot: Autopilot
    for drone in config.drones:
        if drone.backend == "rotorpy":
            autopilot = RotorPyAutopilot(
                drone.model, drone.position, drone.speed, drone.heading
            )
        elif drone.backend == "jsbsim":
            autopilot = JSBSimAutopilot(
                drone.model, drone.position, drone.speed, drone.heading, config.seed
            )
        else:
            raise ValueError(f"unsupported simulation backend: {drone.backend}")
        flights[drone.name] = Flight(autopilot, drone.mission)
    return Simulation(flights)


def create_episode(config: SimulationConfig) -> Episode:
    return Episode(
        lambda: create_simulation(config),
        config.time_step,
        config.duration,
        config.route_changes,
    )


def run(config: SimulationConfig, output: Path) -> dict[str, str]:
    """Run a scenario; keep partial recordings on failure, never overwrite a run."""
    episode = create_episode(config)
    output.mkdir(parents=True, exist_ok=False)
    configuration = asdict(config)
    if not config.route_changes:
        del configuration["route_changes"]
    metadata: RunMetadata = {
        "configuration": configuration,
        "python": python_version(),
        "packages": {
            name: version(name)
            for name in ("uav-onboard-planner", "rotorpy", "jsbsim", "numpy")
        },
        "status": "running",
    }
    metadata_path = output / "run.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (output / "trajectory.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "time_s",
                "drone",
                "east_m",
                "north_m",
                "up_m",
                "ve_m_s",
                "vn_m_s",
                "vu_m_s",
                "status",
                "waypoint",
            ]
        )

        def record(samples: dict[str, FlightSample]) -> None:
            for name, sample in samples.items():
                state = sample.state
                writer.writerow(
                    [
                        state.time,
                        name,
                        *state.position,
                        *state.velocity,
                        sample.status,
                        sample.waypoint,
                    ]
                )

        samples = episode.snapshot()
        record(samples)
        next_sample = config.sample_interval
        while not episode.finished:
            samples = episode.step()
            if episode.time + 1e-9 >= next_sample or episode.finished:
                record(samples)
                next_sample += config.sample_interval
    statuses: dict[str, str] = {name: sample.status for name, sample in samples.items()}
    metadata["status"] = "finished"
    metadata["missions"] = statuses
    metadata["simulated_seconds"] = episode.time
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return statuses
