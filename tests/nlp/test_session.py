import json
from pathlib import Path

import pytest

from uav_onboard_planner.nlp.config import SystemOneConfig, load_prompt
from uav_onboard_planner.nlp.session import Embeddings, Session


def test_session_keeps_original_instruction_through_clarification_and_edit() -> None:
    class Interpreter:
        def __init__(self) -> None:
            self.responses = iter(
                [
                    {"sites": ["dach A", "dach B"]},
                    {"question": "Który dach pominąć?"},
                    {"sites": ["dach A"]},
                ]
            )

        def interpret(self, context: str) -> object:
            if "drugi" in context:
                assert "Który dach pominąć?" in context
                assert "dach B" in context
            return next(self.responses)

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            return Embeddings("test/encoder", "v1", tuple((1.0, 0.0) for _ in texts))

    session = Session(Interpreter(), Encoder())
    first = session.submit("Obejrzyj dach A i dach B")
    assert first.instruction == "USER_INSTRUCTION"
    assert first.sites == ("dach A", "dach B")
    assert session.submit("Pomiń jeden").question == "Który dach pominąć?"
    edit = session.submit("Pomiń drugi")
    assert edit.instruction == "USER_PROMPT"
    assert edit.sites == ("dach A",)
    assert edit.embeddings == Embeddings("test/encoder", "v1", ((1.0, 0.0),))
    assert session.user_instruction == "Obejrzyj dach A i dach B"
    payload = json.loads(edit.to_json())
    assert payload["draft"]["sites"] == ["dach A"]
    assert payload["embeddings"] == {
        "model": "test/encoder",
        "revision": "v1",
        "dimension": 2,
        "fields": {"sites": [[1.0, 0.0]]},
    }


def test_invalid_vectors_do_not_accept_the_instruction() -> None:
    class Interpreter:
        def interpret(self, context: str) -> object:
            return {"sites": ["roof A"]}

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            return Embeddings("test/encoder", "v1", ((float("nan"),),))

    session = Session(Interpreter(), Encoder())
    with pytest.raises(ValueError, match="nieprawidłowe wektory"):
        session.submit("Inspect roof A")
    assert session.user_instruction is None


def test_system_one_profile_accepts_fp16_and_rejects_invalid_context(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile.ini"
    settings = (
        "[systemone]\nmodel = test/model\nrevision = v1\ndevice = cpu\n"
        "dtype = float16\ncontext_size = 256\nmax_new_tokens = 64\nprompt_file = prompt.yaml\n"
    )
    profile.write_text(settings, encoding="utf-8")
    prompt = tmp_path / "prompt.yaml"
    prompt.write_text("system: Draft an inspection.\n", encoding="utf-8")
    config = SystemOneConfig.load(profile)
    assert config.dtype == "float16"
    assert load_prompt(config.prompt_file) == "Draft an inspection."
    profile.write_text(settings.replace("256", "64"), encoding="utf-8")
    with pytest.raises(ValueError, match="context_size"):
        SystemOneConfig.load(profile)
