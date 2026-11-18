import csv
import json
from dataclasses import asdict
from importlib.metadata import version
from math import isclose
from pathlib import Path
from platform import python_version
from typing import NotRequired, TypedDict

from .config import SimulationConfig
from .contracts import Autopilot, FlightState
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


def run(config: SimulationConfig, output: Path) -> dict[str, str]:
    """Run a scenario; keep partial recordings on failure, never overwrite a run."""
    simulation = create_simulation(config)
    output.mkdir(parents=True, exist_ok=False)
    metadata: RunMetadata = {
        "configuration": asdict(config),
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

        def record(states: dict[str, FlightState]) -> None:
            for name, state in states.items():
                flight = simulation.flights[name]
                writer.writerow(
                    [
                        state.time,
                        name,
                        *state.position,
                        *state.velocity,
                        flight.status,
                        flight.waypoint_index,
                    ]
                )

        record(
            {
                name: flight.autopilot.state
                for name, flight in simulation.flights.items()
            }
        )
        next_sample = config.sample_interval
        while simulation.time < config.duration:
            states = simulation.step(
                min(config.time_step, config.duration - simulation.time)
            )
            finished = isclose(simulation.time, config.duration, rel_tol=1e-12)
            if simulation.time + 1e-9 >= next_sample or finished:
                record(states)
                next_sample += config.sample_interval
            if finished:
                break
    statuses: dict[str, str] = {
        name: flight.status for name, flight in simulation.flights.items()
    }
    metadata["status"] = "finished"
    metadata["missions"] = statuses
    metadata["simulated_seconds"] = simulation.time
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return statuses
