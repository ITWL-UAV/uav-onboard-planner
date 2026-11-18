# uav-onboard-planner
Onboard software for autonomous UAV mission planning, execution, and in-flight replanning.

The repository currently contains an initial Python package skeleton. Mission
planning, execution, simulation, and training are not implemented yet.

## Setup

Requires Python 3.12 or newer and `uv`.

```sh
uv sync
uv run python -c "import uav_onboard_planner"
uv run pytest
```

The `dev` dependency group includes the test tools and is installed by default.
The `basic` group is reserved for inference dependencies and is currently empty:

```sh
uv sync --no-default-groups --group basic
```

Build a source distribution and wheel with:

```sh
uv build
```

## Structure

```text
src/
    uav_onboard_planner/
        __init__.py
tests/
    test_package.py
docs/
pyproject.toml
uv.lock
```

`src/uav_onboard_planner/` contains the package; `tests/` contains its tests.
See [PROJECT.md](PROJECT.md) for project requirements and [AGENTS.md](AGENTS.md)
for engineering guidelines and the planned documentation map.
