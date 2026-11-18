import pytest

from uav_onboard_planner.simulation.contracts import FlightState, Mission, Position
from uav_onboard_planner.simulation.episode import Episode
from uav_onboard_planner.simulation.mission import Flight, Simulation
from uav_onboard_planner.simulation.scenario import MissionCancellation, RouteChange
from uav_onboard_planner.simulation.sensors import AltimeterConfig


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


def test_scheduled_cancellation_leaves_other_flight_active_and_replays() -> None:
    def create() -> Simulation:
        mission = Mission(tuple((x, 0, 10) for x in range(1, 6)), 0.1)
        return Simulation(
            {name: Flight(Aircraft(), mission) for name in ("survey", "traffic")}
        )

    episode = Episode(
        create, 0.01, 0.035, cancellations=(MissionCancellation(0.015, "survey"),)
    )

    def trace():
        assert episode.step()["survey"].status == "active"
        boundary = episode.step()
        assert episode.time == pytest.approx(0.015)
        assert boundary["survey"].status == "cancelled"
        assert boundary["traffic"].status == "active"
        assert not episode.finished
        after = episode.step()
        assert after["traffic"].waypoint == boundary["traffic"].waypoint + 1
        assert after["survey"].waypoint == boundary["survey"].waypoint
        assert after["survey"].state.position == boundary["survey"].state.position
        return boundary, after

    first = trace()
    episode.reset()
    assert trace() == first


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


def test_altimeter_releases_delayed_samples_and_replays_noise() -> None:
    def create() -> Simulation:
        mission = Mission(((1, 0, 11), (2, 0, 12), (3, 0, 13)), 0.1)
        return Simulation(
            {name: Flight(Aircraft(), mission) for name in ("survey", "traffic")}
        )

    episode = Episode(
        create,
        0.01,
        0.03,
        altimeters={"survey": AltimeterConfig(noise_std_m=0.2, delay_s=0.015)},
        seed=42,
    )

    def trace():
        assert episode.altitude_observations() == {"survey": None}
        episode.step()
        assert episode.altitude_observations() == {"survey": None}
        episode.step()
        first = episode.altitude_observations()["survey"]
        assert first is not None
        assert first.measured_at_s == 0
        assert first.available_at_s == pytest.approx(0.015)
        assert first.altitude_m != 10
        assert first.altitude_m == pytest.approx(10, abs=1)
        assert episode.altitude_observations()["survey"] == first
        episode.step()
        second = episode.altitude_observations()["survey"]
        assert second is not None
        assert second.measured_at_s == pytest.approx(0.01)
        return first, second

    first_trace = trace()
    episode.reset()
    assert trace() == first_trace


def test_live_mission_commands_apply_between_steps_and_reset() -> None:
    def create() -> Simulation:
        mission = Mission(((1, 0, 10), (2, 0, 10), (3, 0, 10)), 0.1)
        return Simulation(
            {name: Flight(Aircraft(), mission) for name in ("survey", "traffic")}
        )

    episode = Episode(create, 0.01, 0.03)
    first = episode.step()
    with pytest.raises(ValueError, match="above ground"):
        episode.replace_mission("survey", Mission(((0, 0, 0),), 0.1))
    with pytest.raises(ValueError, match="unknown drone"):
        episode.cancel_mission("missing")
    assert episode.snapshot() == first

    episode.replace_mission("survey", Mission(((0, 5, 10), (0, 6, 10)), 0.1))
    assert episode.time == pytest.approx(0.01)
    assert episode.snapshot()["survey"].waypoint == 0
    second = episode.step()
    assert second["survey"].state.position == (0, 5, 10)
    assert second["traffic"].state.position == (2, 0, 10)
    episode.cancel_mission("survey")
    assert episode.snapshot()["survey"].status == "cancelled"

    last = episode.step()
    assert last["survey"].state.position == second["survey"].state.position
    assert last["traffic"].status == "completed"
    with pytest.raises(RuntimeError, match="reset"):
        episode.cancel_mission("survey")

    episode.reset()
    assert episode.step() == first


def test_failed_live_mission_command_requires_reset() -> None:
    class FailingAircraft(Aircraft):
        def set_target(self, target: Position | None) -> None:
            if target is None:
                raise RuntimeError("cannot hold position")
            super().set_target(target)

    def create() -> Simulation:
        return Simulation(
            {"survey": Flight(FailingAircraft(), Mission(((1, 0, 10),), 0.1))}
        )

    episode = Episode(create, 0.01, 0.03)
    with pytest.raises(RuntimeError, match="cannot hold position"):
        episode.cancel_mission("survey")
    with pytest.raises(RuntimeError, match="reset"):
        episode.snapshot()
    with pytest.raises(RuntimeError, match="reset"):
        episode.step()
    episode.reset()
    assert episode.snapshot()["survey"].status == "active"
