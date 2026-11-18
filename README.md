# uav-onboard-planner
Onboard software for autonomous UAV mission planning, execution, and in-flight replanning.

The package includes a local 3D flight simulation for quadrotors and fixed-wing
aircraft, with independent waypoint missions for multiple vehicles. Perception,
decision models, hardware integration, and training are not implemented yet.

## Setup

Requires Python 3.12 or newer and `uv`.

```sh
uv sync
uv run python -c "import uav_onboard_planner"
uv run pytest
```

The `dev` dependency group includes simulation and test tools and is installed by default.
The `basic` group is reserved for inference dependencies and is currently empty:

```sh
uv sync --no-default-groups --group basic
```

Build a source distribution and wheel with:

```sh
uv build
```

Development checks and GitHub Actions are described in
[docs/tooling.md](docs/tooling.md).

## Simulation

```sh
uv run python -m uav_onboard_planner.simulation \
  --config configs/simulation/default.yaml \
  --output /tmp/uav-flight-001
```

Use a new output directory for each run. Results include CSV trajectories,
a 3D plot, configuration, library versions, and mission statuses.
Edit the YAML to change the aircraft, routes, timing, and animation settings.
See [docs/simulation.md](docs/simulation.md) for the configuration contract,
adapter boundaries, licenses, and simulation limitations.

## Structure

```text
src/
    uav_onboard_planner/
        __init__.py
        simulation/
            adapters/
tests/
    test_package.py
    simulation/
configs/
    simulation/
        default.yaml
docs/
    simulation.md
pyproject.toml
uv.lock
```

`src/uav_onboard_planner/` contains the package; `tests/` contains its tests.
See [PROJECT.md](PROJECT.md) for project requirements and [AGENTS.md](AGENTS.md)
for engineering guidelines and the planned documentation map.
