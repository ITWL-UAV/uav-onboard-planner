from math import dist
from typing import Literal

from .contracts import Autopilot, FlightState, Mission, positive


class Flight:
    def __init__(self, autopilot: Autopilot, mission: Mission) -> None:
        self.autopilot = autopilot
        self.replace_mission(mission)

    def replace_mission(self, mission: Mission) -> None:
        self.mission = mission
        self.waypoint_index = 0
        self.status: Literal["active", "completed", "cancelled"] = "active"
        self.autopilot.set_target(mission.waypoints[0])

    def cancel(self) -> None:
        if self.status == "active":
            self.autopilot.set_target(None)
            self.status = "cancelled"

    def step(self, dt: float) -> FlightState:
        positive(dt, "dt")
        state = self.autopilot.step(dt)
        while self.status == "active" and dist(
            state.position, self.mission.waypoints[self.waypoint_index]
        ) <= self.mission.arrival_radius:
            self.waypoint_index += 1
            if self.waypoint_index == len(self.mission.waypoints):
                self.autopilot.set_target(None)
                self.status = "completed"
            else:
                self.autopilot.set_target(self.mission.waypoints[self.waypoint_index])
        return state


class Simulation:
    def __init__(self, flights: dict[str, Flight]) -> None:
        if not flights:
            raise ValueError("simulation needs at least one flight")
        if len({id(f.autopilot) for f in flights.values()}) != len(flights):
            raise ValueError("each flight needs its own autopilot")
        self.flights = dict(flights)
        self.time = 0.0

    def step(self, dt: float) -> dict[str, FlightState]:
        positive(dt, "dt")
        states = {name: flight.step(dt) for name, flight in self.flights.items()}
        self.time += dt
        return states
