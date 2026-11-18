from math import atan2, degrees, radians
from tempfile import TemporaryDirectory

import jsbsim

from ..contracts import FlightState, Position, position, positive

METRES_PER_FOOT = 0.3048
# shortcut: equatorial map for local scenes; use geodetic transforms for larger regions.
EARTH_RADIUS = 6378137.0


class JSBSimAutopilot:
    """C172 dynamics and its bundled heading/altitude autopilot; local equatorial ENU."""

    def __init__(
        self, model: str, initial: Position, speed: float, heading: float, seed: int
    ) -> None:
        if model != "c172x":
            raise ValueError("the current JSBSim adapter supports c172x")
        positive(speed, "speed")
        initial = position(initial)
        self._fdm = jsbsim.FGFDMExec(None)
        self._fdm.set_debug_level(0)
        self._output = TemporaryDirectory(prefix="jsbsim-")
        self._fdm.set_output_path(self._output.name)
        if not self._fdm.load_model(model):
            raise RuntimeError(f"could not load JSBSim model {model}")
        self._fdm.disable_output()
        values = {
            "ic/lat-geod-deg": degrees(initial[1] / EARTH_RADIUS),
            "ic/long-gc-deg": degrees(initial[0] / EARTH_RADIUS),
            "ic/h-sl-ft": initial[2] / METRES_PER_FOOT,
            "ic/terrain-elevation-ft": 0,
            "ic/vt-fps": speed / METRES_PER_FOOT,
            "ic/psi-true-deg": heading,
            "propulsion/set-running": -1,
            "simulation/randomseed": seed,
        }
        for name, value in values.items():
            self._fdm[name] = value
        if not self._fdm.run_ic():
            raise RuntimeError("could not initialize JSBSim flight")
        self._fdm.do_trim(0)
        self._fdm["ap/heading_hold"] = 1
        self._fdm["ap/altitude_hold"] = 1
        self._target: Position | None = None
        self.set_target(None)

    @property
    def state(self) -> FlightState:
        fdm = self._fdm
        return FlightState(
            fdm.get_sim_time(),
            (
                radians(fdm["position/long-gc-deg"]) * EARTH_RADIUS,
                radians(fdm["position/lat-geod-deg"]) * EARTH_RADIUS,
                fdm["position/h-sl-ft"] * METRES_PER_FOOT,
            ),
            (
                fdm["velocities/v-east-fps"] * METRES_PER_FOOT,
                fdm["velocities/v-north-fps"] * METRES_PER_FOOT,
                -fdm["velocities/v-down-fps"] * METRES_PER_FOOT,
            ),
        )

    def set_target(self, target: Position | None) -> None:
        self._target = None if target is None else position(target)
        if target is None:
            self._fdm["ap/heading_setpoint"] = self._fdm["attitude/psi-deg"]
            self._fdm["ap/altitude_setpoint"] = self._fdm["position/h-sl-ft"]

    def step(self, dt: float) -> FlightState:
        positive(dt, "dt")
        if dt > 0.02:
            raise ValueError("dt must not exceed 0.02 s")
        if self._target is not None:
            current = self.state.position
            east, north, altitude = self._target
            self._fdm["ap/heading_setpoint"] = degrees(atan2(east - current[0], north - current[1])) % 360
            self._fdm["ap/altitude_setpoint"] = altitude / METRES_PER_FOOT
        self._fdm.set_dt(dt)
        if not self._fdm.run():
            raise RuntimeError("JSBSim stopped before completing the simulation step")
        state = self.state
        if state.position[2] <= 0:
            raise RuntimeError("fixed-wing aircraft reached the ground")
        return state
