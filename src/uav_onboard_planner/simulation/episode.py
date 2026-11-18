from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from math import isclose
from typing import Literal

from .contracts import FlightState, positive
from .mission import Simulation
from .scenario import RouteChange, schedule


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
    ) -> None:
        positive(time_step, "time_step")
        positive(duration, "duration")
        self._create_simulation = create_simulation
        self._time_step = time_step
        self._duration = duration
        self._changes = changes
        self.reset()

    def reset(self) -> None:
        simulation = self._create_simulation()
        self._pending = deque(
            schedule(self._changes, simulation.flights, self._duration)
        )
        self._simulation = simulation
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

    def step(self) -> dict[str, FlightSample]:
        if self._failed or self.finished:
            raise RuntimeError("reset the episode before stepping again")
        boundary = self._pending[0].time if self._pending else self._duration
        dt = min(self._time_step, boundary - self.time)
        try:
            self._simulation.step(dt)
            while self._pending and self._pending[0].time <= self.time:
                change = self._pending.popleft()
                self._simulation.flights[change.drone].replace_mission(change.mission)
            return self.snapshot()
        except Exception:
            self._failed = True
            raise
