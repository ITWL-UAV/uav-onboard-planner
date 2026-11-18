from collections import deque
from dataclasses import dataclass
from math import isfinite
from random import Random


@dataclass(frozen=True)
class AltimeterConfig:
    """Noise and delay of a simulated altitude measurement."""

    noise_std_m: float
    delay_s: float

    def __post_init__(self) -> None:
        for field, value in (
            ("noise_std_m", self.noise_std_m),
            ("delay_s", self.delay_s),
        ):
            if isinstance(value, bool) or not isfinite(value) or value < 0:
                raise ValueError(f"altimeter {field} must be finite and nonnegative")


@dataclass(frozen=True)
class AltitudeMeasurement:
    """Height in metres above local ground; timestamps in simulation seconds."""

    altitude_m: float
    measured_at_s: float
    available_at_s: float


class SimulatedAltimeter:
    def __init__(self, config: AltimeterConfig, random: Random) -> None:
        self._config = config
        self._random = random
        self._pending: deque[AltitudeMeasurement] = deque()
        self.latest: AltitudeMeasurement | None = None
        self.released: tuple[AltitudeMeasurement, ...] = ()

    def sample(self, time_s: float, altitude_m: float) -> None:
        self._pending.append(
            AltitudeMeasurement(
                altitude_m + self._random.gauss(0, self._config.noise_std_m),
                time_s,
                time_s + self._config.delay_s,
            )
        )
        released = []
        while self._pending and self._pending[0].available_at_s <= time_s:
            released.append(self._pending.popleft())
        self.released = tuple(released)
        if released:
            self.latest = released[-1]
