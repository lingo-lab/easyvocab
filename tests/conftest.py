from typing import Any

import pytest

from easyvocab import DeckTemplate, LLMCardGenerator, WordInput
from easyvocab.testing import FakeLLM
from helpers import de_output, word_from_messages


@pytest.fixture
def de_template() -> DeckTemplate:
    return DeckTemplate.builtin("de-en-a1b1")


@pytest.fixture
def en_template() -> DeckTemplate:
    return DeckTemplate.builtin("en-ru")


@pytest.fixture
def valid_output() -> dict[str, Any]:
    return de_output()


@pytest.fixture
def echo_llm() -> FakeLLM:
    """Answers every word with a valid card for that word."""
    return FakeLLM(respond=lambda messages: de_output(word_from_messages(messages)))


@pytest.fixture
def generator(echo_llm: FakeLLM, de_template: DeckTemplate) -> LLMCardGenerator:
    return LLMCardGenerator(echo_llm, de_template)


@pytest.fixture
def words() -> list[WordInput]:
    return [WordInput(word=word) for word in ("Haus", "Baum", "Tisch")]
