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
    from uav_onboard_planner.nlp.config import (
        PromptProfile,
        SystemOneConfig,
        load_prompt,
    )
    from uav_onboard_planner.nlp.scenario import load_conversation
    from uav_onboard_planner.nlp.session import Embeddings, Session

    settings = SystemOneConfig.load(Path("configs/nlp/systemone/default.ini"))
    profile = load_prompt(settings.prompt_file)
    assert isinstance(profile, PromptProfile)
    system = profile.prompts["SYSTEM"]
    general = profile.prompts["GENERAL_INSTRUCTION"]
    conversation = load_conversation(
        Path("scenarios/clarifications.yaml"), "missing-destination", 5
    )
    assert conversation == load_conversation(
        Path("scenarios/clarifications.yaml"), "missing-destination", 5
    )
    assert [turn.time for turn in conversation.turns] == [0.0, 2.0, 6.0, 9.0]

    class Interpreter:
        def __init__(self) -> None:
            self.responses = iter(
                [
                    {"activity": "transport"},
                    {
                        "activity": "deliver",
                        "target": "crate A to point B",
                    },
                    {
                        "change": "Use point C",
                        "target": "crate A to point C",
                    },
                    {
                        "change": "Deliver before 14:00",
                        "target": "crate A to point C",
                        "constraints": ["Before 14:00"],
                    },
                ]
            )

        def interpret(self, context: str) -> object:
            request = json.loads(context)
            assert "expected" not in request
            assert request["instruction"] in ("USER_INSTRUCTION", "USER_PROMPT")
            assert request["system"] == {
                "text": system.default_text,
                "fields": system.default_fields,
            }
            if request["instruction"] == "USER_INSTRUCTION":
                active = request["active_instruction"]
                assert "target" not in active["fields"]
                assert active["fields"] == json.loads(
                    json.dumps(general.default_fields)
                )
            else:
                assert request["active_instruction"]["fields"] == {
                    "activity": "deliver",
                    "target": "crate A to point B",
                }
            assert all(
                set(field) == {"question", "type", "required", "embed"}
                and field["question"].endswith("?")
                and field["embed"] is True
                for field in request["fields"].values()
            )
            assert request["fields"]["constraints"]["required"] is False
            assert request["fields"]["target"]["type"] == "text"
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
    run_replay(session(), conversation, replay_out, metadata)
    assert [json.loads(line) for line in terminal_out.getvalue().splitlines()] == [
        json.loads(line) for line in replay_out.getvalue().splitlines()
    ]
    replies = [json.loads(line) for line in replay_out.getvalue().splitlines()]
    expected_turns = [
        ("Deliver crate A.", "CLARIFICATION", None),
        ("Deliver it to point B.", "USER_INSTRUCTION", "crate A to point B"),
        ("Deliver it to point C instead.", "USER_PROMPT", "crate A to point C"),
        ("Deliver it before 14:00.", "USER_PROMPT", "crate A to point C"),
    ]
    assert [
        (
            turn.text,
            reply.get(
                "instruction", "CLARIFICATION" if reply.get("question") else None
            ),
            reply.get("draft", {}).get("target"),
        )
        for turn, reply in zip(conversation.turns, replies, strict=True)
    ] == expected_turns
    assert "target" in replies[0]["question"]
    last = json.loads(replay_out.getvalue().splitlines()[-1])
    assert last["embeddings"]["fields"]["target"] == [1.0]
    assert last["draft"]["constraints"] == ["Before 14:00"]
    assert last["embeddings"]["fields"]["constraints"] == [[1.0]]
    record = json.loads(metadata.getvalue())
    assert record["conversation"] == "missing-destination"
    assert record["seed"] == 5
    assert [turn["text"] for turn in record["turns"]] == [
        turn.text for turn in conversation.turns
    ]
