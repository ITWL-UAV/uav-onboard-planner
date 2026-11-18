from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import yaml

from .contracts import Mission, Position, position, positive


@dataclass(frozen=True)
class DroneConfig:
    name: str
    backend: str
    model: str
    position: Position
    speed: float
    heading: float
    mission: Mission


@dataclass(frozen=True)
class SimulationConfig:
    time_step: float
    duration: float
    sample_interval: float
    seed: int
    show_animation: bool
    drones: tuple[DroneConfig, ...]


def load_config(path: Path) -> SimulationConfig:
    """Load and validate a scenario before initializing any simulation library."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "time_step",
            "duration",
            "sample_interval",
            "seed",
            "show_animation",
            "drones",
        }:
            raise ValueError(
                "invalid simulation fields; see configs/simulation/default.yaml"
            )
        for key in ("time_step", "duration", "sample_interval"):
            positive(data[key], key)
        if data["time_step"] > 0.02:
            raise ValueError(
                "time_step must not exceed 0.02 s for the current adapters"
            )
        if data["sample_interval"] < data["time_step"]:
            raise ValueError("sample_interval must be at least time_step")
        if type(data["seed"]) is not int or not 0 <= data["seed"] < 2**32:
            raise ValueError("seed must be an integer in [0, 2**32)")
        if type(data["show_animation"]) is not bool:
            raise ValueError("show_animation must be a boolean")
        if not isinstance(data["drones"], list) or not data["drones"]:
            raise ValueError("drones must be a nonempty list")
        drones = []
        for drone in data["drones"]:
            if not isinstance(drone, dict) or set(drone) != {
                "name",
                "backend",
                "model",
                "position",
                "speed",
                "heading",
                "arrival_radius",
                "waypoints",
            }:
                raise ValueError("invalid drone fields")
            if not isinstance(drone["name"], str) or not drone["name"].strip():
                raise ValueError("drone name must be a nonempty string")
            if drone["backend"] not in ("rotorpy", "jsbsim"):
                raise ValueError("backend must be rotorpy or jsbsim")
            models = {"rotorpy": ("hummingbird", "crazyflie"), "jsbsim": ("c172x",)}
            if drone["model"] not in models[drone["backend"]]:
                raise ValueError("model is not supported by the selected adapter")
            initial = position(drone["position"])
            if initial[2] <= 0:
                raise ValueError("aircraft must start above ground")
            positive(drone["speed"], "speed")
            if not isfinite(drone["heading"]) or isinstance(drone["heading"], bool):
                raise ValueError("heading must be finite")
            mission = Mission(drone["waypoints"], drone["arrival_radius"])
            if any(p[2] <= 0 for p in mission.waypoints):
                raise ValueError("waypoints must be above ground")
            drones.append(
                DroneConfig(
                    drone["name"],
                    drone["backend"],
                    drone["model"],
                    initial,
                    drone["speed"],
                    drone["heading"],
                    mission,
                )
            )
        if len({d.name for d in drones}) != len(drones):
            raise ValueError("drone names must be unique")
        return SimulationConfig(
            data["time_step"],
            data["duration"],
            data["sample_interval"],
            data["seed"],
            data["show_animation"],
            tuple(drones),
        )
    except (yaml.YAMLError, TypeError, KeyError, OverflowError) as error:
        raise ValueError(f"invalid simulation configuration: {error}") from error
