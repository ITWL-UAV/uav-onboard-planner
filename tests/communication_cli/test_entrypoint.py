import io
import json
import subprocess
import sys
from pathlib import Path

from uav_onboard_planner.communication_cli.__main__ import run_replay, run_terminal
from uav_onboard_planner.nlp.config import PromptProfile, load_prompt
from uav_onboard_planner.nlp.scenario import load_conversation
from uav_onboard_planner.nlp.session import Embeddings, Session

TESTS = Path(__file__).resolve().parents[1]


def test_operator_cli_is_available_as_a_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "uav_onboard_planner.communication_cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--text" in result.stdout
    assert "--scenario" in result.stdout


def test_terminal_and_replay_return_the_same_replies() -> None:
    profile = load_prompt(TESTS / "fixtures" / "cargo_profile.yaml")
    assert isinstance(profile, PromptProfile)
    conversation = load_conversation(
        TESTS / "scenarios" / "clarifications.yaml", "missing-destination", seed=1
    )
    answers = {
        "Transport crate A.": {},
        "Deliver it to point B.": {"target": "point B"},
        "Deliver it to point C before 14:00.": {
            "change": "Change the destination and delivery time",
            "target": "point C",
            "constraints": ["Before 14:00"],
        },
    }

    class Interpreter:
        def interpret(self, context: str) -> object:
            return answers[json.loads(context)["operator_message"]]

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            return Embeddings("encoder", "v1", tuple((1.0,) for _ in texts))

    terminal_out, replay_out, metadata = io.StringIO(), io.StringIO(), io.StringIO()
    terminal_in = io.StringIO("".join(f"{turn.text}\n" for turn in conversation.turns))
    run_terminal(
        Session(Interpreter(), Encoder(), profile),
        terminal_in,
        terminal_out,
        io.StringIO(),
    )
    run_replay(
        Session(Interpreter(), Encoder(), profile), conversation, replay_out, metadata
    )

    assert terminal_out.getvalue() == replay_out.getvalue()
    clarification, instruction, change = map(
        json.loads, replay_out.getvalue().splitlines()
    )
    assert "target" in clarification["question"]
    assert (instruction["instruction"], instruction["draft"]["target"]) == (
        "USER_INSTRUCTION",
        "point B",
    )
    assert (change["instruction"], change["draft"]["target"]) == (
        "USER_PROMPT",
        "point C",
    )
    assert change["draft"]["constraints"] == ["Before 14:00"]
    assert json.loads(metadata.getvalue()) == {
        "conversation": "missing-destination",
        "seed": 1,
        "turns": [
            {"time": 0, "text": "Transport crate A."},
            {"time": 2, "text": "Deliver it to point B."},
            {"time": 6, "text": "Deliver it to point C before 14:00."},
        ],
    }
