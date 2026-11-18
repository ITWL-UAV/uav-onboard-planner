import json
from pathlib import Path

import pytest

from uav_onboard_planner.nlp.config import load_prompt
from uav_onboard_planner.nlp.session import Embeddings, Session


def test_general_defaults_must_match_the_user_instruction_schema(
    tmp_path: Path,
) -> None:
    template = Path("configs/nlp/prompts/inspection_template.yaml")
    path = tmp_path / template.name
    path.write_text(
        template.read_text(encoding="utf-8").replace(
            "sites: [designated area]", "sites: []"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"GENERAL_INSTRUCTION\.default_fields.*sites"):
        load_prompt(path)


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
    assert session.initial == ()
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
