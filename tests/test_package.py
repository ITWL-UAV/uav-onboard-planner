from importlib import import_module


def test_package_imports() -> None:
    assert import_module("uav_onboard_planner").__name__ == "uav_onboard_planner"
