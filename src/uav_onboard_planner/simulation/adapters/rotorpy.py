from copy import deepcopy
from math import radians, sqrt

import numpy as np
from rotorpy.controllers.quadrotor_control import SE3Control
from rotorpy.vehicles.crazyflie_params import quad_params as crazyflie
from rotorpy.vehicles.hummingbird_params import quad_params as hummingbird
from rotorpy.vehicles.multirotor import Multirotor

from ..contracts import FlightState, Position, position, positive


class RotorPyAutopilot:
    def __init__(self, model: str, initial: Position, speed: float, heading: float) -> None:
        positive(speed, "speed")
        params = deepcopy({"hummingbird": hummingbird, "crazyflie": crazyflie}[model])
        params["motor_noise_std"] = 0.0
        self._vehicle = Multirotor(params)
        self._controller = SE3Control(params)
        self._yaw = radians(90 - heading)
        self._raw = {
            "x": np.array(position(initial), dtype=float),
            "v": np.zeros(3),
            "q": np.array([0, 0, np.sin(self._yaw / 2), np.cos(self._yaw / 2)]),
            "w": np.zeros(3),
            "wind": np.zeros(3),
            "rotor_speeds": np.full(4, sqrt(params["mass"] * 9.81 / (4 * params["k_eta"]))),
        }
        self._speed = speed
        self._time = 0.0
        self._reference = self._raw["x"].copy()
        self._target = self._reference.copy()

    @property
    def state(self) -> FlightState:
        return FlightState(self._time, tuple(self._raw["x"]), tuple(self._raw["v"]))

    def set_target(self, target: Position | None) -> None:
        if target is None:
            self._reference = self._raw["x"].copy()
            self._target = self._reference.copy()
        else:
            self._target = np.array(position(target), dtype=float)

    def step(self, dt: float) -> FlightState:
        positive(dt, "dt")
        if dt > 0.02:
            raise ValueError("dt must not exceed 0.02 s")
        offset = self._target - self._reference
        distance = np.linalg.norm(offset)
        velocity = np.zeros(3)
        if distance > 0:
            movement = min(distance, self._speed * dt)
            self._reference += offset * (movement / distance)
            if movement < distance:
                velocity = offset * (self._speed / distance)
        flat = {
            "x": self._reference.copy(), "x_dot": velocity,
            "x_ddot": np.zeros(3), "x_dddot": np.zeros(3), "x_ddddot": np.zeros(3),
            "yaw": self._yaw, "yaw_dot": 0.0,
        }
        control = self._controller.update(self._time, self._raw, flat)
        self._raw = self._vehicle.step(self._raw, control, dt)
        self._time += dt
        state = self.state
        if state.position[2] <= 0:
            raise RuntimeError("quadrotor reached the ground")
        return state
