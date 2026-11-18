import json

from uav_onboard_planner.nlp.huggingface import _extract_fields


def test_optional_activity_does_not_block_a_destination_answer() -> None:
    context = json.dumps(
        {
            "operator_message": "To point B.",
            "fields": {
                "activity": {
                    "question": "What action?",
                    "type": "text",
                    "required": False,
                },
                "target": {
                    "question": "What destination?",
                    "type": "text",
                    "required": True,
                },
            },
        }
    )
    answers = iter(["Clarify: What action should I take?", "point B"])
    assert _extract_fields(context, lambda _: next(answers)) == {"target": "point B"}


def test_extraction_asks_one_question_per_field_and_parses_text_answers() -> None:
    prompts = []
    answers = iter(["transport", "cargo: crate A\ndestination: point B", "N/A"])

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    context = json.dumps(
        {
            "operator_message": "Deliver crate A to point B.",
            "fields": {
                "activity": {"question": "What action?", "type": "text"},
                "target": {"question": "What does it concern?", "type": "text_map"},
                "constraints": {"question": "What limits apply?", "type": "text_list"},
            },
        }
    )

    assert _extract_fields(context, generate) == {
        "activity": "transport",
        "target": {"cargo": "crate A", "destination": "point B"},
    }
    assert len(prompts) == 3
    for prompt, question in zip(
        prompts,
        ["What action?", "What does it concern?", "What limits apply?"],
        strict=True,
    ):
        assert question in prompt
        assert "Deliver crate A to point B." in prompt
        assert "JSON" not in prompt


def test_extraction_preserves_list_order_and_stops_at_clarification() -> None:
    context = json.dumps(
        {
            "fields": {
                "target": {"question": "Which sites?", "type": "text_map"},
                "constraints": {"question": "What limits?", "type": "text_list"},
            },
        }
    )
    answers = iter(["sites[]: roof B\nsites[]: roof A", "15 min\nDaylight only"])
    assert _extract_fields(context, lambda _: next(answers)) == {
        "target": {"sites": ["roof B", "roof A"]},
        "constraints": ["15 min", "Daylight only"],
    }

    clarification = iter(["Clarify: Which roof?"])
    assert _extract_fields(context, lambda _: next(clarification)) == {
        "question": "Which roof?"
    }


def test_first_instruction_extracts_one_target_phrase_from_operator() -> None:
    prompts = []
    answers = iter(["crate A to point B"])

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    context = json.dumps(
        {
            "instruction": "USER_INSTRUCTION",
            "active_instruction": {"text": "Use the designated delivery point"},
            "operator_message": "Deliver crate A to point B.",
            "fields": {
                "target": {"question": "What does the action concern?", "type": "text"},
            },
        }
    )
    assert _extract_fields(context, generate) == {"target": "crate A to point B"}
    assert len(prompts) == 1
    assert "What does the action concern?" in prompts[0]
    assert "designated delivery point" not in prompts[0]
