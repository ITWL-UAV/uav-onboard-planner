from math import dist

import pytest

from uav_onboard_planner.simulation.adapters.jsbsim import JSBSimAutopilot
from uav_onboard_planner.simulation.adapters.rotorpy import RotorPyAutopilot
from uav_onboard_planner.simulation.contracts import Mission
from uav_onboard_planner.simulation.mission import Flight


@pytest.mark.integration
def test_quadrotor_reaches_waypoint_and_hovers() -> None:
    autopilot = RotorPyAutopilot("hummingbird", (0, 0, 10), 2, 0)
    flight = Flight(autopilot, Mission(((5, 0, 10),), 0.3))
    for _ in range(1500):
        state = flight.step(0.01)
    assert flight.status == "completed"
    assert dist(state.position, (5, 0, 10)) < 0.6
    assert dist(state.velocity, (0, 0, 0)) < 0.1


@pytest.mark.integration
def test_fixed_wing_reaches_waypoints_and_keeps_flying() -> None:
    autopilot = JSBSimAutopilot("c172x", (0, 0, 300), 50, 0, 42)
    flight = Flight(autopilot, Mission(((0, 500, 300), (500, 1200, 300)), 60))
    for _ in range(4000):
        state = flight.step(0.01)
    assert flight.status == "completed"
    assert state.position[0] > 400
    assert state.position[1] > 1000
    assert abs(state.position[2] - 300) < 30
    assert dist(state.velocity, (0, 0, 0)) > 30


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["rotorpy", "jsbsim"])
def test_adapters_are_repeatable(backend: str) -> None:
    def run():
        if backend == "rotorpy":
            aircraft = RotorPyAutopilot("crazyflie", (0, 0, 10), 1, 0)
        else:
            aircraft = JSBSimAutopilot("c172x", (0, 0, 300), 50, 0, 42)
        aircraft.set_target((10, 100, aircraft.state.position[2]))
        for _ in range(100):
            aircraft.step(0.01)
        return aircraft.state

    assert run() == run()
