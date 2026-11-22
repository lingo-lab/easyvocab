from collections.abc import Sequence
from typing import Any

import pytest
from inline_snapshot import snapshot

from easyvocab import DeckTemplate, LLMCardGenerator, Usage, WordInput
from easyvocab.errors import GenerationError, LLMError
from easyvocab.models import Completion, Message
from easyvocab.testing import FakeLLM


def test_generates_a_card_with_metadata(de_template: DeckTemplate, valid_output: dict[str, Any]) -> None:
    llm = FakeLLM([valid_output], usage=Usage(1000, 200, 800), cost_usd=0.0004)
    card = LLMCardGenerator(llm, de_template).generate(WordInput(word="Haus"))
    assert card.fields == valid_output
    assert card.model_dump(include={"template", "model", "attempts", "usage", "cost_usd"}) == snapshot(
        {
            "template": "de-en-a1b1",
            "model": "fake-model",
            "attempts": 1,
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cached_prompt_tokens": 800},
            "cost_usd": 0.0004,
        }
    )
    assert card.template_fingerprint == de_template.fingerprint


def test_invalid_reply_gets_feedback_and_retry(de_template: DeckTemplate, valid_output: dict[str, Any]) -> None:
    broken = {**valid_output, "examples": []}
    llm = FakeLLM(["not json at all", broken, valid_output])
    card = LLMCardGenerator(llm, de_template).generate(WordInput(word="Haus"))
    assert card.attempts == 3
    assert card.cost_usd == pytest.approx(0.003)
    assert card.usage == Usage(300, 150, 0)
    retry_messages = llm.calls[2]
    assert retry_messages[-4].content == "not json at all"
    assert "no JSON object" in retry_messages[-3].content
    assert "examples" in retry_messages[-1].content


def test_gives_up_after_max_attempts(de_template: DeckTemplate) -> None:
    llm = FakeLLM(["nope", "still nope"])
    with pytest.raises(GenerationError, match="after 2 attempts") as error:
        LLMCardGenerator(llm, de_template, max_attempts=2).generate(WordInput(word="Haus"))
    assert error.value.word == "Haus"


def test_unknown_cost_stays_unknown(de_template: DeckTemplate, valid_output: dict[str, Any]) -> None:
    llm = FakeLLM([valid_output], cost_usd=None)
    assert LLMCardGenerator(llm, de_template).generate(WordInput(word="Haus")).cost_usd is None


class FailingLLM(FakeLLM):
    def complete(self, messages: Sequence[Message]) -> Completion:
        raise LLMError("server exploded")


def test_llm_errors_become_generation_errors(de_template: DeckTemplate) -> None:
    with pytest.raises(GenerationError, match="server exploded"):
        LLMCardGenerator(FailingLLM(), de_template).generate(WordInput(word="Haus"))


def test_fingerprint_depends_on_llm(de_template: DeckTemplate) -> None:
    first = LLMCardGenerator(FakeLLM(model="a"), de_template).fingerprint
    assert first == LLMCardGenerator(FakeLLM(model="a"), de_template).fingerprint
    assert first != LLMCardGenerator(FakeLLM(model="b"), de_template).fingerprint


def test_preflight_checks_template_and_llm(de_template: DeckTemplate) -> None:
    llm = FakeLLM()
    LLMCardGenerator(llm, de_template).preflight()
    assert llm.preflight_calls == 1
    with pytest.raises(ValueError, match="at least 1"):
        LLMCardGenerator(llm, de_template, max_attempts=0)
