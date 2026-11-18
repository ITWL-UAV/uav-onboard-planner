from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isclose
from random import Random
from typing import Literal

from .contracts import FlightState, Mission, positive
from .mission import Simulation
from .scenario import MissionCancellation, RouteChange, schedule, validate_route_change
from .sensors import AltimeterConfig, AltitudeMeasurement, SimulatedAltimeter


@dataclass(frozen=True)
class FlightSample:
    state: FlightState
    status: Literal["active", "completed", "cancelled"]
    waypoint: int


class Episode:
    def __init__(
        self,
        create_simulation: Callable[[], Simulation],
        time_step: float,
        duration: float,
        changes: tuple[RouteChange, ...] = (),
        *,
        cancellations: tuple[MissionCancellation, ...] = (),
        altimeters: Mapping[str, AltimeterConfig] | None = None,
        seed: int = 0,
    ) -> None:
        positive(time_step, "time_step")
        positive(duration, "duration")
        self._create_simulation = create_simulation
        self._time_step = time_step
        self._duration = duration
        self._events: tuple[RouteChange | MissionCancellation, ...] = (
            changes + cancellations
        )
        self._altimeter_configs = dict(altimeters or {})
        self._seed = seed
        self.reset()

    def reset(self) -> None:
        simulation = self._create_simulation()
        if self._altimeter_configs.keys() - simulation.flights.keys():
            raise ValueError("altimeter configured for an unknown flight")
        altimeters = {
            name: SimulatedAltimeter(config, Random(f"{self._seed}:{name}"))
            for name, config in self._altimeter_configs.items()
        }
        for name, altimeter in altimeters.items():
            altimeter.sample(0.0, simulation.flights[name].autopilot.state.position[2])
        self._pending = deque(
            schedule(self._events, simulation.flights, self._duration)
        )
        self._simulation = simulation
        self._altimeters = altimeters
        self._failed = False

    @property
    def time(self) -> float:
        return self._simulation.time

    @property
    def finished(self) -> bool:
        return not self._pending and isclose(self.time, self._duration, rel_tol=1e-12)

    def snapshot(self) -> dict[str, FlightSample]:
        if self._failed:
            raise RuntimeError("reset the episode after a failed step")
        return {
            name: FlightSample(
                flight.autopilot.state, flight.status, flight.waypoint_index
            )
            for name, flight in self._simulation.flights.items()
        }

    def altitude_observations(self) -> dict[str, AltitudeMeasurement | None]:
        """Return the latest available measurement for each equipped flight."""
        if self._failed:
            raise RuntimeError("reset the episode after a failed step")
        return {name: sensor.latest for name, sensor in self._altimeters.items()}

    def altitude_updates(self) -> dict[str, tuple[AltitudeMeasurement, ...]]:
        """Return measurements made available at the current simulation step."""
        if self._failed:
            raise RuntimeError("reset the episode after a failed step")
        return {
            name: sensor.released
            for name, sensor in self._altimeters.items()
            if sensor.released
        }

    def replace_mission(self, drone: str, mission: Mission) -> None:
        """Replace the flight's mission at the current simulation time."""
        self._command_mission(drone, mission)

    def cancel_mission(self, drone: str) -> None:
        """Cancel the flight's active mission at the current simulation time."""
        self._command_mission(drone, None)

    def _command_mission(self, drone: str, mission: Mission | None) -> None:
        if self._failed or self.finished:
            raise RuntimeError("reset the episode before issuing a mission command")
        if drone not in self._simulation.flights:
            raise ValueError(f"unknown drone: {drone!r}")
        if mission is not None:
            validate_route_change(mission)
        try:
            self._apply_mission(drone, mission)
        except Exception:
            self._failed = True
            raise

    def _apply_mission(self, drone: str, mission: Mission | None) -> None:
        flight = self._simulation.flights[drone]
        if mission is None:
            flight.cancel()
        else:
            flight.replace_mission(mission)

    def step(self) -> dict[str, FlightSample]:
        if self._failed or self.finished:
            raise RuntimeError("reset the episode before stepping again")
        boundary = self._pending[0].time if self._pending else self._duration
        dt = min(self._time_step, boundary - self.time)
        try:
            states = self._simulation.step(dt)
            while self._pending and self._pending[0].time <= self.time:
                event = self._pending.popleft()
                mission = event.mission if isinstance(event, RouteChange) else None
                self._apply_mission(event.drone, mission)
            for name, altimeter in self._altimeters.items():
                altimeter.sample(self.time, states[name].position[2])
            return self.snapshot()
        except Exception:
            self._failed = True
            raise
