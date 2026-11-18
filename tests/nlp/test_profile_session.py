import json
from pathlib import Path

import pytest

from uav_onboard_planner.nlp.config import load_prompt
from uav_onboard_planner.nlp.session import Embeddings, Session

CARGO_PROFILE = Path(__file__).resolve().parents[1] / "fixtures" / "cargo_profile.yaml"


def test_general_defaults_reject_unknown_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / CARGO_PROFILE.name
    path.write_text(
        CARGO_PROFILE.read_text(encoding="utf-8").replace(
            "GENERAL_INSTRUCTION:\n  source: profile\n  fields:\n",
            "GENERAL_INSTRUCTION:\n  source: profile\n  fields:\n    unexpected: value\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"GENERAL_INSTRUCTION\.fields.*unexpected"):
        load_prompt(path)


def test_operator_requires_a_boolean_per_field(tmp_path: Path) -> None:
    path = tmp_path / CARGO_PROFILE.name
    path.write_text(
        CARGO_PROFILE.read_text(encoding="utf-8").replace(
            "constraints: false", "constraints: 'false'", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"USER_INSTRUCTION\.required"):
        load_prompt(path)


def test_transport_requires_one_text_target_from_the_operator() -> None:
    profile = load_prompt(CARGO_PROFILE)
    responses = iter(
        [
            {
                "activity": "transport",
                "target": {"cargo": "crate A", "destination": "point B"},
            },
            {"activity": "transport"},
            {
                "activity": "transport",
                "target": "point B",
            },
            {
                "change": "Use point C",
                "target": "point C",
            },
        ]
    )

    class Interpreter:
        def interpret(self, context: str) -> object:
            return next(responses)

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            assert texts in (
                ("transport", "point B"),
                ("Use point C", "point C"),
            )
            return Embeddings("encoder", "v1", ((1.0,), (2.0,)))

    session = Session(Interpreter(), Encoder(), profile)
    assert "target" not in session.mission.active.fields
    with pytest.raises(ValueError, match="target"):
        session.submit("Deliver crate A to point B.")
    assert session.user_instruction is None

    incomplete = session.submit("Deliver crate A.")
    assert incomplete.question and "target" in incomplete.question
    assert session.user_instruction is None

    reply = json.loads(session.submit("To point B.").to_json())
    assert reply["instruction"] == "USER_INSTRUCTION"
    assert reply["draft"]["target"] == "point B"
    assert reply["embeddings"]["fields"]["target"] == [2.0]

    assert session.submit("Use point C.").instruction == "USER_PROMPT"
    assert session.mission.active.fields["activity"] == "transport"


def test_profile_drives_hierarchy_and_validates_before_encoding(tmp_path: Path) -> None:
    path = tmp_path / "park.yaml"
    path.write_text(
        """
schema_version: 1
SYSTEM:
  source: profile
  default_text: Document public parks.
  fields:
    purpose: {meaning: Purpose, type: text, required: true, embed: false}
GENERAL_INSTRUCTION:
  source: profile
  default_text: Survey the trees.
  fields:
    objective: {meaning: Task, type: text, required: true, embed: true}
    subjects: {meaning: Subjects, type: text_list, required: false, embed: true}
USER_INSTRUCTION:
  source: operator
  default_text: null
  fields:
    objective: {meaning: Task, type: text, required: true, embed: true}
    subjects: {meaning: Subjects, type: text_list, required: false, embed: true}
USER_PROMPT:
  source: operator
  default_text: null
  fields:
    change: {meaning: Edit, type: text, required: true, embed: true}
    applies_to: {meaning: Part, type: text, required: false, embed: false}
""",
        encoding="utf-8",
    )
    profile = load_prompt(path)
    contexts = []
    responses = iter(
        [
            {"objective": "Map paths", "subjects": []},
            {"change": "Start at entrance"},
            {"objective": "New task"},
            {"question": "Które alejki?"},
            {"change": "Map all paths", "applies_to": "paths"},
            {"change": "Stop after the main path"},
            {},
        ]
    )
    batches = []

    class Interpreter:
        def interpret(self, context: str) -> object:
            contexts.append(json.loads(context))
            return next(responses)

    class Encoder:
        def encode(self, texts: tuple[str, ...]) -> Embeddings:
            batches.append(texts)
            vectors = tuple((float(index),) for index, _ in enumerate(texts))
            if texts == ("Stop after the main path",):
                vectors = ((float("nan"),),)
            return Embeddings("test/encoder", "v1", vectors)

    session = Session(Interpreter(), Encoder(), profile)
    assert contexts == []
    assert batches == []
    assert session.mission.active.text == "Survey the trees."
    assert session.mission.active.fields == {}

    first = json.loads(session.submit("Zmapuj alejki").to_json())
    assert first["instruction"] == "USER_INSTRUCTION"
    assert first["draft"] == {"objective": "Map paths"}
    assert first["embeddings"]["fields"] == {"objective": [0.0]}
    assert session.mission.active.fields == {"objective": "Map paths"}
    assert contexts[0]["system"] == {"text": "Document public parks.", "fields": {}}
    assert contexts[0]["active_instruction"] == {
        "text": "Survey the trees.",
        "fields": {},
    }

    assert session.submit("Zacznij przy wejściu").instruction == "USER_PROMPT"
    with pytest.raises(ValueError, match="objective"):
        session.submit("Zmień cel")
    assert session.submit("Zmień zakres").question == "Które alejki?"
    edit = json.loads(session.submit("Wszystkie").to_json())
    assert edit["draft"]["applies_to"] == "paths"
    assert edit["embeddings"]["fields"] == {"change": [0.0]}
    assert session.user_instruction == "Zmapuj alejki"
    assert session.mission.system.text == "Document public parks."
    assert [change.fields["change"] for change in session.mission.changes] == [
        "Start at entrance",
        "Map all paths",
    ]
    assert contexts[-1]["pending_clarification"] == ["Zmień zakres", "Które alejki?"]
    assert contexts[-1]["active_instruction"]["fields"] == {"objective": "Map paths"}

    with pytest.raises(ValueError, match="nieprawidłowe wektory"):
        session.submit("Zmiana")
    assert session.submit("Jeszcze inaczej").question is not None
    assert len(session.mission.changes) == 2
    assert batches == [
        ("Map paths",),
        ("Start at entrance",),
        ("Map all paths",),
        ("Stop after the main path",),
    ]

    path.write_text(
        path.read_text().replace("embed: false", "other: false"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="SYSTEM.purpose"):
        load_prompt(path)
