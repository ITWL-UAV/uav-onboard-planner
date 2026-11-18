from dataclasses import dataclass
from math import isfinite
from typing import Protocol

Position = tuple[float, float, float]


def positive(value: float, name: str) -> None:
    if isinstance(value, bool) or not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def position(value: Position) -> Position:
    if len(value) != 3 or any(isinstance(v, bool) or not isfinite(v) for v in value):
        raise ValueError("position must contain three finite coordinates")
    return value[0], value[1], value[2]


@dataclass(frozen=True)
class FlightState:
    """Time in seconds; position in local ENU metres; velocity in ENU m/s."""

    time: float
    position: Position
    velocity: Position

    def __post_init__(self) -> None:
        if not isfinite(self.time) or self.time < 0:
            raise ValueError("time must be finite and nonnegative")
        object.__setattr__(self, "position", position(self.position))
        object.__setattr__(self, "velocity", position(self.velocity))


@dataclass(frozen=True)
class Mission:
    """Ordered ENU waypoints in metres; arrival radius in metres."""

    waypoints: tuple[Position, ...]
    arrival_radius: float

    def __post_init__(self) -> None:
        if not self.waypoints:
            raise ValueError("mission must have at least one waypoint")
        object.__setattr__(
            self, "waypoints", tuple(position(p) for p in self.waypoints)
        )
        positive(self.arrival_radius, "arrival_radius")


class Autopilot(Protocol):
    @property
    def state(self) -> FlightState: ...

    def set_target(self, target: Position | None) -> None:
        """Set a waypoint; None requests hover or heading/altitude hold."""
        ...

    def step(self, dt: float) -> FlightState:
        """Advance simulated flight by dt seconds and return ground truth."""
        ...
