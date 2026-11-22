from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from easyvocab import BatchGenerator, CardCache, DeckTemplate, LLMCardGenerator, WordInput
from easyvocab.errors import ConfigurationError
from easyvocab.models import Message
from easyvocab.testing import FakeLLM
from helpers import de_output, word_from_messages


def test_generates_in_input_order_and_caches(
    generator: LLMCardGenerator, words: list[WordInput], tmp_path: Path
) -> None:
    llm = generator.llm
    assert isinstance(llm, FakeLLM)
    with CardCache(tmp_path / "cache.sqlite") as cache:
        first = BatchGenerator(generator, cache=cache, workers=3).run(words)
    assert [card.word.word for card in first.cards] == ["Haus", "Baum", "Tisch"]
    assert (first.cached, first.generated, len(llm.calls)) == (0, 3, 3)
    assert first.cost_usd == pytest.approx(0.003)

    with CardCache(tmp_path / "cache.sqlite") as cache:
        second = BatchGenerator(generator, cache=cache).run([*words, WordInput(word="Stuhl")])
        assert len(cache) == 4
    assert (second.cached, second.generated, len(llm.calls)) == (3, 1, 4)
    assert second.cards[0] == first.cards[0]


def test_duplicates_are_generated_once(generator: LLMCardGenerator) -> None:
    result = BatchGenerator(generator).run([WordInput(word="Haus"), WordInput(word="Haus")])
    assert len(result.cards) == 1
    assert result.generated == 1


def test_per_word_failures_are_collected(de_template: DeckTemplate) -> None:
    def reply(messages: Sequence[Message]) -> str | dict[str, Any]:
        word = word_from_messages(messages)
        return "garbage" if word == "Baum" else de_output(word)

    generator = LLMCardGenerator(FakeLLM(respond=reply), de_template, max_attempts=2)
    result = BatchGenerator(generator, workers=2).run([WordInput(word="Haus"), WordInput(word="Baum")])
    assert [card.word.word for card in result.cards] == ["Haus"]
    assert list(result.failures) == ["Baum"]
    assert "2 attempts" in result.failures["Baum"]


def test_fatal_errors_stop_the_run(de_template: DeckTemplate, words: list[WordInput]) -> None:
    def reply(messages: Sequence[Message]) -> dict[str, Any]:
        raise ConfigurationError("bad key")

    generator = LLMCardGenerator(FakeLLM(respond=reply), de_template)
    with pytest.raises(ConfigurationError, match="bad key"):
        BatchGenerator(generator).run(words)


def test_cache_key_changes_with_template_model_and_context(
    de_template: DeckTemplate, en_template: DeckTemplate
) -> None:
    word = WordInput(word="Haus")
    key = CardCache.key(LLMCardGenerator(FakeLLM(model="a"), de_template), word)
    assert key == CardCache.key(LLMCardGenerator(FakeLLM(model="a"), de_template), word)
    assert key != CardCache.key(LLMCardGenerator(FakeLLM(model="b"), de_template), word)
    assert key != CardCache.key(LLMCardGenerator(FakeLLM(model="a"), en_template), word)
    assert key != CardCache.key(LLMCardGenerator(FakeLLM(model="a"), de_template), WordInput(word="Haus", context="x"))
