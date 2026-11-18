import json
from pathlib import Path

import pytest
import yaml

from uav_onboard_planner.nlp.config import PromptProfile, load_prompt
from uav_onboard_planner.nlp.session import Embeddings, Interpretation, Session

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CARGO_PROFILE = FIXTURES / "cargo_profile.yaml"
LEGACY_PROFILE = FIXTURES / "legacy_profile.yaml"


class Interpreter:
    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.requests: list[dict[str, object]] = []

    def interpret(self, context: str) -> object:
        request = json.loads(context)
        self.requests.append(request)
        return self.answers[request["operator_message"]]


class Encoder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def encode(self, texts: tuple[str, ...]) -> Embeddings:
        self.calls.append(texts)
        return Embeddings(
            "encoder", "v1", tuple((float(i),) for i, _ in enumerate(texts, 1))
        )


@pytest.mark.parametrize(
    "profile,field_path,value,error",
    [
        pytest.param(
            CARGO_PROFILE,
            "GENERAL_INSTRUCTION.fields.unexpected",
            "value",
            r"GENERAL_INSTRUCTION\.fields.*unexpected",
            id="unknown-default-field",
        ),
        pytest.param(
            CARGO_PROFILE,
            "USER_INSTRUCTION.required.constraints",
            "false",
            r"USER_INSTRUCTION\.required",
            id="required-must-be-boolean",
        ),
        pytest.param(
            LEGACY_PROFILE,
            "SYSTEM.fields.purpose",
            {},
            r"SYSTEM\.purpose",
            id="incomplete-legacy-definition",
        ),
    ],
)
def test_profile_rejects_invalid_fields(
    tmp_path: Path,
    profile: Path,
    field_path: str,
    value: object,
    error: str,
) -> None:
    data = yaml.safe_load(profile.read_text(encoding="utf-8"))
    section, block, key = field_path.split(".")
    data[section][block][key] = value
    path = tmp_path / profile.name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        load_prompt(path)


@pytest.fixture
def cargo_profile() -> PromptProfile:
    profile = load_prompt(CARGO_PROFILE)
    assert isinstance(profile, PromptProfile)
    return profile


def test_missing_destination_requests_clarification(
    cargo_profile: PromptProfile,
) -> None:
    first, answer = "Deliver crate A.", "To point B."
    interpreter = Interpreter(
        {first: {"activity": "deliver"}, answer: {"target": "point B"}}
    )
    encoder = Encoder()
    session = Session(interpreter, encoder, cargo_profile)

    assert session.mission is not None
    assert "target" not in session.mission.active.fields
    assert not interpreter.requests and not encoder.calls

    incomplete = session.submit(first)
    assert incomplete.missing_required == ("target",)
    assert session.user_instruction is None
    assert not encoder.calls

    instruction = session.submit(answer)
    assert instruction.instruction == "USER_INSTRUCTION"
    assert instruction.draft == {"target": "point B"}
    assert instruction.vectors_by_field == {"target": (1.0,)}
    assert interpreter.requests[-1]["pending_clarification"] == [first]


def test_destination_must_be_text(cargo_profile: PromptProfile) -> None:
    message = "Deliver crate A to point B."
    encoder = Encoder()
    session = Session(
        Interpreter({message: {"target": {"destination": "point B"}}}),
        encoder,
        cargo_profile,
    )

    with pytest.raises(ValueError, match="target"):
        session.submit(message)
    assert session.user_instruction is None
    assert not encoder.calls


def test_low_confidence_requires_a_more_precise_prompt(
    cargo_profile: PromptProfile,
) -> None:
    first, precise = "Deliver near point B.", "Deliver to point B."
    interpreter = Interpreter(
        {
            first: Interpretation({"target": "point B."}, {"target": 0.59}),
            precise: Interpretation({"target": "point B."}, {"target": 0.6}),
        }
    )
    encoder = Encoder()
    session = Session(interpreter, encoder, cargo_profile)

    reply = session.submit(first)
    assert reply.draft == {"target": "point B."}
    assert reply.confidence == {"target": 0.59}
    assert reply.low_confidence == ("target",)
    assert reply.needs_clarification
    assert session.user_instruction is None
    assert not encoder.calls

    assert not session.submit(precise).needs_clarification
    assert session.user_instruction == precise
    assert encoder.calls == [("point B.",)]


def test_invalid_edits_preserve_original_instruction(
    cargo_profile: PromptProfile,
) -> None:
    first = "Deliver crate A to point B."
    edit = "Use point C."
    invalid = "Change the task to inspection."
    failed = "Use point D."
    interpreter = Interpreter(
        {
            first: {"activity": "deliver", "target": "point B"},
            edit: {"change": "Change destination", "target": "point C"},
            invalid: {"activity": "inspect", "target": "point E"},
            failed: {"change": "Change destination", "target": "point D"},
        }
    )

    class FailingEncoder(Encoder):
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            if "point D" in texts:
                return Embeddings("encoder", "v1", ((1.0,), (float("nan"),)))
            return super().encode(texts)

    session = Session(interpreter, FailingEncoder(), cargo_profile)
    assert session.submit(first).instruction == "USER_INSTRUCTION"
    assert session.submit(edit).instruction == "USER_PROMPT"
    with pytest.raises(ValueError, match="activity"):
        session.submit(invalid)
    with pytest.raises(ValueError, match="nieprawidłowe wektory"):
        session.submit(failed)

    assert session.user_instruction == first
    assert session.mission is not None
    assert session.mission.active.fields == {"activity": "deliver", "target": "point B"}
    assert [change.fields["target"] for change in session.mission.changes] == [
        "point C"
    ]


def test_legacy_profile_embeds_only_selected_fields() -> None:
    first, edit = "Map paths.", "Start at the entrance."
    encoder = Encoder()
    session = Session(
        Interpreter(
            {
                first: {"objective": "Map paths", "subjects": []},
                edit: {"change": "Start at the entrance", "applies_to": "paths"},
            }
        ),
        encoder,
        load_prompt(LEGACY_PROFILE),
    )

    assert session.submit(first).draft == {"objective": "Map paths"}
    reply = session.submit(edit)
    assert reply.draft == {"change": "Start at the entrance", "applies_to": "paths"}
    assert encoder.calls == [("Map paths",), ("Start at the entrance",)]
