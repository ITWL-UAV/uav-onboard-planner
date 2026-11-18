from collections.abc import Collection
from dataclasses import dataclass

from .contracts import Mission, positive


@dataclass(frozen=True)
class RouteChange:
    """Replace the named vehicle's route at time seconds from episode start."""

    time: float
    drone: str
    mission: Mission


def schedule(
    changes: tuple[RouteChange, ...], drones: Collection[str], duration: float
) -> tuple[RouteChange, ...]:
    seen: set[tuple[float, str]] = set()
    for change in changes:
        positive(change.time, "route change time")
        if change.time >= duration:
            raise ValueError("route change time must be before episode end")
        if change.drone not in drones:
            raise ValueError(f"unknown drone in route change: {change.drone!r}")
        if any(p[2] <= 0 for p in change.mission.waypoints):
            raise ValueError("route change waypoints must be above ground")
        key = (change.time, change.drone)
        if key in seen:
            raise ValueError(
                f"conflicting route changes for {change.drone} at {change.time} s"
            )
        seen.add(key)
    return tuple(sorted(changes, key=lambda change: change.time))
