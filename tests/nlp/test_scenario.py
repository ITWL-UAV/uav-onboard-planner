from pathlib import Path

import pytest

from uav_onboard_planner.nlp.scenario import Replay, load_conversation
from uav_onboard_planner.nlp.session import Embeddings, Session


def test_replay_waits_for_simulation_time_and_retries_a_failed_turn(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scenario.yaml"
    path.write_text(
        "survey:\n"
        "  - {time: 2, text: Inspect roof A}\n"
        "  - {time: 4, text: Start at the entrance}\n"
        "  - {time: 4, text: Then continue around it}\n",
        encoding="utf-8",
    )
    conversation = load_conversation(path, "survey", seed=0)

    class Interpreter:
        def interpret(self, context: str) -> object:
            return {"sites": ["roof A"]}

    class Encoder:
        def __init__(self) -> None:
            self.calls = 0

        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            self.calls += 1
            if self.calls == 2:
                raise ValueError("encoding failed")
            return Embeddings("encoder", "v1", ((1.0,),))

    replay = Replay(Session(Interpreter(), Encoder()), conversation)
    assert list(replay.advance(1.9)) == []
    assert [reply.instruction for _, reply in replay.advance(2)] == ["USER_INSTRUCTION"]
    assert list(replay.advance(3)) == []
    with pytest.raises(ValueError, match="encoding failed"):
        list(replay.advance(4))
    assert [(turn.text, reply.instruction) for turn, reply in replay.advance(4)] == [
        ("Start at the entrance", "USER_PROMPT"),
        ("Then continue around it", "USER_PROMPT"),
    ]
    assert list(replay.advance(4)) == []
    with pytest.raises(ValueError, match="monotonic"):
        list(replay.advance(3))


@pytest.mark.parametrize("time", ["-1", ".nan", ".inf", "true", "1", "9" * 400])
def test_scenario_rejects_invalid_times(time: str, tmp_path: Path) -> None:
    path = tmp_path / "scenario.yaml"
    path.write_text(
        f"survey:\n  - {{time: 2, text: First}}\n  - {{time: {time}, text: Second}}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="turn 2"):
        load_conversation(path, "survey", seed=0)
