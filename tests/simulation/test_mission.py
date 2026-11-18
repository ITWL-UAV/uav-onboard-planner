import pytest

from uav_onboard_planner.simulation.contracts import FlightState, Mission, Position
from uav_onboard_planner.simulation.mission import Flight, Simulation


class Aircraft:
    def __init__(self) -> None:
        self.state = FlightState(0.0, (0.0, 0.0, 10.0), (0.0, 0.0, 0.0))
        self.target: Position | None = None

    def set_target(self, target: Position | None) -> None:
        self.target = target

    def step(self, dt: float) -> FlightState:
        self.state = FlightState(
            self.state.time + dt, self.target or self.state.position, (0.0, 0.0, 0.0)
        )
        return self.state


def test_multiple_flights_progress_independently() -> None:
    first = Flight(Aircraft(), Mission(((1.0, 0.0, 10.0), (2.0, 0.0, 10.0)), 0.1))
    second = Flight(Aircraft(), Mission(((0.0, 3.0, 10.0),), 0.1))
    simulation = Simulation({"first": first, "second": second})
    states = simulation.step(0.1)
    assert states["first"].position == (1.0, 0.0, 10.0)
    assert first.status == "active"
    assert second.status == "completed"
    simulation.step(0.1)
    assert first.status == "completed"
    assert simulation.time == pytest.approx(0.2)


def test_cancel_releases_route_and_replacement_starts_new_mission() -> None:
    aircraft = Aircraft()
    flight = Flight(aircraft, Mission(((10.0, 0.0, 10.0),), 0.1))
    flight.cancel()
    flight.step(0.1)
    assert flight.status == "cancelled"
    assert aircraft.target is None
    assert aircraft.state.position == (0.0, 0.0, 10.0)
    flight.replace_mission(Mission(((0.0, 10.0, 10.0),), 0.1))
    flight.step(0.1)
    assert flight.status == "completed"
    assert aircraft.state.position == (0.0, 10.0, 10.0)


@pytest.mark.parametrize("dt", [0, -1, float("nan"), float("inf")])
def test_invalid_step_does_not_advance_aircraft(dt: float) -> None:
    aircraft = Aircraft()
    simulation = Simulation({"drone": Flight(aircraft, Mission(((1, 0, 10),), 1))})
    with pytest.raises(ValueError):
        simulation.step(dt)
    assert aircraft.state.time == 0


@pytest.mark.parametrize("points,radius", [([], 1), ([(0, 0, 1)], 0), ([(0, 0, float("nan"))], 1)])
def test_invalid_missions_are_rejected(points, radius) -> None:
    with pytest.raises(ValueError):
        Mission(points, radius)
