from random import Random

from uav_onboard_planner.simulation.sensors import AltimeterConfig, SimulatedAltimeter


def test_altimeter_releases_every_sample_ready_on_the_same_step() -> None:
    altimeter = SimulatedAltimeter(AltimeterConfig(0, 0.008), Random(42))
    altimeter.sample(0, 10)
    altimeter.sample(0.01, 11)
    altimeter.sample(0.015, 12)
    assert altimeter.released == ()

    altimeter.sample(0.025, 13)
    assert [sample.altitude_m for sample in altimeter.released] == [11, 12]
    assert altimeter.latest == altimeter.released[-1]
