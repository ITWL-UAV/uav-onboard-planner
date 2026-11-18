import pytest

from uav_onboard_planner.simulation.contracts import FlightState, Mission, Position
from uav_onboard_planner.simulation.episode import Episode
from uav_onboard_planner.simulation.mission import Flight, Simulation
from uav_onboard_planner.simulation.scenario import RouteChange


class Aircraft:
    def __init__(self) -> None:
        self.state = FlightState(0, (0, 0, 10), (0, 0, 0))
        self.target: Position | None = None

    def set_target(self, target: Position | None) -> None:
        self.target = target

    def step(self, dt: float) -> FlightState:
        self.state = FlightState(
            self.state.time + dt, self.target or self.state.position, (0, 0, 0)
        )
        return self.state


def test_scheduled_route_change_after_first_waypoint_and_reset() -> None:
    def create() -> Simulation:
        return Simulation(
            {"survey": Flight(Aircraft(), Mission(((1, 0, 10), (2, 0, 10)), 0.1))}
        )

    episode = Episode(
        create, 0.01, 0.03, (RouteChange(0.015, "survey", Mission(((3, 0, 10),), 0.1)),)
    )

    def trace():
        samples = [episode.snapshot()]
        while not episode.finished:
            samples.append(episode.step())
        return samples

    first = trace()
    assert first[1]["survey"].state.position == (1, 0, 10)
    assert first[2]["survey"].state.time == pytest.approx(0.015)
    assert first[2]["survey"].state.position == (2, 0, 10)
    assert first[2]["survey"].status == "active"
    assert first[3]["survey"].state.position == (3, 0, 10)
    assert first[-1]["survey"].status == "completed"
    with pytest.raises(RuntimeError):
        episode.step()

    episode.reset()
    assert trace() == first
