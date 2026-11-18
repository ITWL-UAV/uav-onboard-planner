from collections import deque
from dataclasses import dataclass
from math import isfinite
from random import Random
from typing import Literal

type AltimeterStatus = Literal["not_equipped", "waiting", "unavailable", "available"]


@dataclass(frozen=True)
class AltimeterOutage:
    """Half-open interval of unavailability in simulation seconds."""

    start_s: float
    end_s: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.start_s, bool)
            or isinstance(self.end_s, bool)
            or not isfinite(self.start_s)
            or not isfinite(self.end_s)
            or not 0 <= self.start_s < self.end_s
        ):
            raise ValueError("altimeter outage requires finite 0 <= start_s < end_s")


@dataclass(frozen=True)
class AltimeterConfig:
    """Noise, delay and scheduled availability of altitude measurements."""

    noise_std_m: float
    delay_s: float
    outages: tuple[AltimeterOutage, ...] = ()

    def __post_init__(self) -> None:
        for field, value in (
            ("noise_std_m", self.noise_std_m),
            ("delay_s", self.delay_s),
        ):
            if isinstance(value, bool) or not isfinite(value) or value < 0:
                raise ValueError(f"altimeter {field} must be finite and nonnegative")
        if any(
            left.end_s > right.start_s
            for left, right in zip(self.outages, self.outages[1:])
        ):
            raise ValueError("altimeter outages must be ordered and non-overlapping")


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
        self._outages = deque(config.outages)
        self._unavailable = False
        self.latest: AltitudeMeasurement | None = None
        self.released: tuple[AltitudeMeasurement, ...] = ()

    @property
    def status(self) -> AltimeterStatus:
        if self._unavailable:
            return "unavailable"
        return "available" if self.latest is not None else "waiting"

    def sample(self, time_s: float, altitude_m: float) -> None:
        if self._outages and self._outages[0].start_s <= time_s:
            self._pending.clear()
            self.latest = None
            while self._outages and self._outages[0].end_s <= time_s:
                self._outages.popleft()
        self._unavailable = bool(self._outages and self._outages[0].start_s <= time_s)
        if self._unavailable:
            self.released = ()
            return
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
