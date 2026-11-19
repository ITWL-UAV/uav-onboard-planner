import json

from uav_onboard_planner.nlp.huggingface import Options, _extract_fields
from uav_onboard_planner.nlp.session import Interpretation


def test_extraction_selects_verbatim_text_and_records_scores() -> None:
    questions = iter(["What action?", "What destination?", "What limits?"])
    answers = iter([("Transport", 0.95), ("point B?", 0.8), (None, 0.9)])

    def choose(prompt: str, options: Options) -> tuple[int, float]:
        assert next(questions) in prompt
        assert "designated delivery point" not in prompt
        quote, score = next(answers)
        return options.index(quote), score

    context = json.dumps(
        {
            "instruction": "USER_INSTRUCTION",
            "operator_message": "Transport crate A to point B?",
            "active_instruction": {"text": "Use the designated delivery point"},
            "fields": {
                "activity": {"question": "What action?", "type": "text"},
                "target": {"question": "What destination?", "type": "text"},
                "constraints": {"question": "What limits?", "type": "text_list"},
            },
        }
    )
    assert _extract_fields(context, choose) == Interpretation(
        {"activity": "Transport", "target": "point B?"},
        {"activity": 0.95, "target": 0.8, "constraints": 0.9},
    )


def test_extraction_preserves_order_in_a_quoted_list() -> None:
    message = "Daylight only.\n15 min."
    context = json.dumps(
        {
            "operator_message": message,
            "fields": {
                "constraints": {"question": "What limits?", "type": "text_list"}
            },
        }
    )

    def choose(prompt: str, options: Options) -> tuple[int, float]:
        return options.index(message), 0.9

    assert _extract_fields(context, choose).fields == {
        "constraints": ["Daylight only.", "15 min."]
    }
