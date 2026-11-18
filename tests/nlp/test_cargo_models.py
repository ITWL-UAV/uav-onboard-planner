import json
from os import getenv
from pathlib import Path

import pytest

from uav_onboard_planner.nlp.config import (
    EmbeddingConfig,
    PromptProfile,
    SystemOneConfig,
    load_prompt,
)
from uav_onboard_planner.nlp.huggingface import HuggingFaceEncoder, HuggingFaceSystemOne
from uav_onboard_planner.nlp.session import Session


@pytest.mark.skipif(
    getenv("UAV_TEST_MODELS") != "1",
    reason="set UAV_TEST_MODELS=1 to run with the configured model weights",
)
def test_transport_instruction_with_configured_models() -> None:
    systemone = SystemOneConfig.load(Path("configs/nlp/systemone/default.ini"))
    embeddings = EmbeddingConfig.load(Path("configs/nlp/embeddings/default.ini"))
    profile = load_prompt(systemone.prompt_file)
    assert isinstance(profile, PromptProfile)
    session = Session(
        HuggingFaceSystemOne(systemone, profile),
        HuggingFaceEncoder(embeddings),
        profile,
    )

    operator_message = "Transport crate A to point B."
    expected_instruction = "USER_INSTRUCTION"
    expected_target = "crate A to point B"
    reply = json.loads(session.submit(operator_message).to_json())
    assert reply.get("instruction") == expected_instruction, (operator_message, reply)
    assert reply["draft"]["activity"].casefold() == "transport"
    assert reply["draft"]["target"].casefold().rstrip(".") == expected_target
    assert (
        len(reply["embeddings"]["fields"]["target"]) == reply["embeddings"]["dimension"]
    )
    assert reply["embeddings"]["dimension"] > 0
