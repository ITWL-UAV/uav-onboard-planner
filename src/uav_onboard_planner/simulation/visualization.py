import csv
from pathlib import Path
from typing import cast


def plot_trajectories(output: Path, show_animation: bool) -> None:
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.animation import FuncAnimation
    from mpl_toolkits.mplot3d.art3d import Line3D  # type: ignore[import-untyped]

    trajectories: dict[str, list[list[float]]] = {}
    with (output / "trajectory.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            trajectories.setdefault(row["drone"], []).append(
                [float(row[key]) for key in ("time_s", "east_m", "north_m", "up_m")]
            )
    arrays = {name: np.array(points) for name, points in trajectories.items()}
    figure = plt.figure(figsize=(6 * (len(arrays) + 1), 5))
    axes = figure.add_subplot(1, len(arrays) + 1, 1, projection="3d")
    views = [(axes, arrays)]
    for index, (name, points) in enumerate(arrays.items(), start=2):
        detail = figure.add_subplot(1, len(arrays) + 1, index, projection="3d")
        views.append((detail, {name: points}))
    for view, tracks in views:
        view.set(xlabel="East [m]", ylabel="North [m]", zlabel="Up [m]")
        for name, points in tracks.items():
            view.plot(points[:, 1], points[:, 2], points[:, 3], label=name)
        view.legend()
    figure.tight_layout()
    figure.savefig(output / "trajectory.png", dpi=150)
    if show_animation:
        lines = {
            name: cast(Line3D, axes.plot([], [], [], marker="o", markersize=3)[0])
            for name in arrays
        }
        times = next(iter(arrays.values()))[:, 0]

        def update(frame: int):
            axes.set_title(f"t = {times[frame]:.2f} s")
            for name, line in lines.items():
                points = arrays[name][: frame + 1]
                line.set_data_3d(points[:, 1], points[:, 2], points[:, 3])
            return tuple(lines.values())

        interval = 1000 * (times[1] - times[0]) if len(times) > 1 else 100
        animation = FuncAnimation(
            figure, update, frames=len(times), interval=interval, repeat=False
        )
        plt.show()
        del animation
    plt.close(figure)
