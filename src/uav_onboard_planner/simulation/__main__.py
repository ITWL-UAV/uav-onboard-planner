import argparse
from pathlib import Path

from .config import load_config
from .runner import run
from .visualization import plot_trajectories


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate aircraft waypoint missions.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory for this run")
    args = parser.parse_args()
    config = load_config(args.config)
    statuses = run(config, args.output)
    plot_trajectories(args.output, config.show_animation)
    for name, status in statuses.items():
        print(f"{name}: {status}")
    print(f"Results: {args.output.resolve()}")


if __name__ == "__main__":
    main()
