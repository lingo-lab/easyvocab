"""Real API smoke test: `make test-live` (needs FIREWORKS_API_KEY, costs well under $0.01)."""

import os
from pathlib import Path

import pytest

from easyvocab import AnkiPackageExporter, DeckTemplate, LLMCardGenerator, OpenAICompatibleLLM, Pipeline, WordInput

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("FIREWORKS_API_KEY"), reason="FIREWORKS_API_KEY is not set"),
]


def test_two_german_words_end_to_end(tmp_path: Path) -> None:
    template = DeckTemplate.builtin("de-en-a1b1")
    generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
    words = [WordInput(word="Fahrrad"), WordInput(word="aufstehen")]
    exporter = AnkiPackageExporter(tmp_path / "deck.apkg", "easyvocab live test")

    result = Pipeline(generator, exporter, workdir=tmp_path).run(words)

    assert result.failures == {}
    fahrrad, aufstehen = result.cards
    assert (fahrrad.fields["pos"], fahrrad.fields["article"]) == ("noun", "das")
    assert (aufstehen.fields["separable"], aufstehen.fields["auxiliary"]) == (True, "sein")
    assert all(card.cost_usd and card.cost_usd < 0.01 for card in result.cards)
    assert (tmp_path / "deck.apkg").stat().st_size > 0

    rerun = Pipeline(generator, exporter, workdir=tmp_path, preflight=False).run(words)
    assert (rerun.batch.cached, rerun.batch.generated) == (2, 0)
