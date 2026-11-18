import subprocess
import sys


def test_operator_cli_is_available_as_a_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "uav_onboard_planner.communication_cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--text" in result.stdout
    assert "--systemone-config" in result.stdout


def test_terminal_and_scenario_produce_the_same_replies() -> None:
    import io
    import json
    from pathlib import Path

    from uav_onboard_planner.communication_cli.__main__ import run_replay, run_terminal
    from uav_onboard_planner.nlp.config import SystemOneConfig, load_prompt
    from uav_onboard_planner.nlp.scenario import load_conversation
    from uav_onboard_planner.nlp.session import Embeddings, Session

    settings = SystemOneConfig.load(Path("configs/nlp/systemone/default.ini"))
    profile = load_prompt(settings.prompt_file)
    conversation = load_conversation(
        Path("scenarios/clarifications.yaml"), "roof-selection", 5
    )
    assert conversation == load_conversation(
        Path("scenarios/clarifications.yaml"), "roof-selection", 5
    )
    assert [turn.time for turn in conversation.turns] == [0.0, 2.0, 6.0, 9.0]

    class Interpreter:
        def __init__(self) -> None:
            self.responses = iter(
                [
                    {"objective": "Survey the area and document building exteriors"},
                    {"question": "Który dach?"},
                    {
                        "objective": "Inspect roof A",
                        "sites": ["dach A"],
                        "constraints": ["Zachowaj odległość 3 m."],
                    },
                    {"change": "Begin with gutters", "sites": ["dach A"]},
                    {"change": "Begin with the facade", "sites": ["dach A"]},
                ]
            )

        def interpret(self, context: str) -> object:
            request = json.loads(context)
            assert "expected" not in request
            assert request["instruction"] != "SYSTEM"
            assert request["system"] == {
                "text": "Serve as a civilian platform for aerial inspection of building exteriors.",
                "fields": {},
            }
            if request["instruction"] == "GENERAL_INSTRUCTION":
                assert "Survey the designated area" in request["profile_text"]
            assert all(
                set(field) == {"question", "type", "required", "embed"}
                and field["question"].endswith("?")
                for field in request["fields"].values()
            )
            return next(self.responses)

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            return Embeddings("encoder", "v1", tuple((1.0,) for _ in texts))

    def session() -> Session:
        return Session(Interpreter(), Encoder(), profile)

    terminal_out = io.StringIO()
    replay_out = io.StringIO()
    metadata = io.StringIO()
    terminal_in = io.StringIO("".join(f"{turn.text}\n" for turn in conversation.turns))
    run_terminal(session(), terminal_in, terminal_out, io.StringIO())
    assert run_replay(session(), conversation, replay_out, metadata, check=True) == 0
    assert [json.loads(line) for line in terminal_out.getvalue().splitlines()] == [
        json.loads(line) for line in replay_out.getvalue().splitlines()
    ]
    assert [
        json.loads(line).get("instruction")
        for line in replay_out.getvalue().splitlines()
    ] == [None, "USER_INSTRUCTION", "USER_PROMPT", "USER_PROMPT"]
    first = json.loads(replay_out.getvalue().splitlines()[1])
    assert first["draft"]["constraints"] == ["Zachowaj odległość 3 m."]
    assert first["embeddings"]["fields"]["constraints"] == [[1.0]]
    record = json.loads(metadata.getvalue())
    assert record["conversation"] == "roof-selection"
    assert record["seed"] == 5
    assert record["mismatches"] == []
    assert [turn["text"] for turn in record["turns"]] == [
        turn.text for turn in conversation.turns
    ]
