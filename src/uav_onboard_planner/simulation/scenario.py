from collections.abc import Collection
from dataclasses import dataclass

from .contracts import Mission, positive


@dataclass(frozen=True)
class RouteChange:
    """Replace the named vehicle's route at time seconds from episode start."""

    time: float
    drone: str
    mission: Mission


@dataclass(frozen=True)
class MissionCancellation:
    """Cancel the named vehicle's active mission at a simulation time in seconds."""

    time: float
    drone: str


def validate_route_change(mission: Mission) -> None:
    if any(point[2] <= 0 for point in mission.waypoints):
        raise ValueError("route change waypoints must be above ground")


def schedule[Event: RouteChange | MissionCancellation](
    events: tuple[Event, ...], drones: Collection[str], duration: float
) -> tuple[Event, ...]:
    seen: set[tuple[float, str]] = set()
    for event in events:
        kind = (
            "route change" if isinstance(event, RouteChange) else "mission cancellation"
        )
        positive(event.time, f"{kind} time")
        if event.time >= duration:
            raise ValueError(f"{kind} time must be before episode end")
        if event.drone not in drones:
            raise ValueError(f"unknown drone in {kind}: {event.drone!r}")
        if isinstance(event, RouteChange):
            validate_route_change(event.mission)
        key = (event.time, event.drone)
        if key in seen:
            conflict = (
                "route changes" if isinstance(event, RouteChange) else "mission events"
            )
            raise ValueError(
                f"conflicting {conflict} for {event.drone} at {event.time} s"
            )
        seen.add(key)
    return tuple(sorted(events, key=lambda event: event.time))
