from pathlib import Path

import pytest

from easyvocab import DeckTemplate, LLMCardGenerator, Pipeline, WordInput
from easyvocab.errors import ConfigurationError, PreflightError, RateLimitedError, TemplateMismatchError
from easyvocab.testing import FakeExporter, FakeLLM, FakeTTS


class BrokenLLM(FakeLLM):
    def preflight(self) -> None:
        raise ConfigurationError("No API key for Fireworks")


class BrokenExporter(FakeExporter):
    def preflight(self, template: DeckTemplate) -> None:
        raise ConfigurationError("Anki is closed")


class QuotaTTS(FakeTTS):
    def preflight(self, lang: str) -> None:
        raise RateLimitedError("Google TTS")


def test_end_to_end_and_resume(generator: LLMCardGenerator, words: list[WordInput], tmp_path: Path) -> None:
    exporter = FakeExporter()
    pipeline = Pipeline(generator, exporter, tts=FakeTTS(), workdir=tmp_path)
    result = pipeline.run(words)
    assert result.export.notes == 3
    assert result.missing_audio == 0
    assert all(len(card.audio) == 3 for card in exporter.cards)
    assert exporter.media_dir == tmp_path / "media"
    assert (tmp_path / "cache.sqlite").is_file()

    tts = FakeTTS()
    rerun = Pipeline(generator, FakeExporter(), tts=tts, workdir=tmp_path).run(words)
    assert (rerun.batch.cached, rerun.batch.generated, tts.texts) == (3, 0, [])
    assert rerun.cards[0].audio == result.cards[0].audio


def test_preflight_reports_all_problems_before_spending(de_template: DeckTemplate, tmp_path: Path) -> None:
    llm = BrokenLLM()
    pipeline = Pipeline(LLMCardGenerator(llm, de_template), BrokenExporter(), tts=FakeTTS(), workdir=tmp_path)
    with pytest.raises(PreflightError) as error:
        pipeline.run([WordInput(word="Haus")])
    assert error.value.problems == ["No API key for Fireworks", "Anki is closed"]
    assert llm.calls == []


def test_tts_quota_at_preflight_is_only_a_warning(generator: LLMCardGenerator, tmp_path: Path) -> None:
    Pipeline(generator, FakeExporter(), tts=QuotaTTS(), workdir=tmp_path).preflight()


def test_without_tts_and_without_preflight(generator: LLMCardGenerator, tmp_path: Path) -> None:
    result = Pipeline(generator, BrokenExporter(), workdir=tmp_path, preflight=False).run([WordInput(word="Haus")])
    assert result.cards[0].audio == {}
    assert result.failures == {}


def test_inputs_are_verified_first(en_template: DeckTemplate, tmp_path: Path) -> None:
    en_template.config.input_vars.append("level")
    pipeline = Pipeline(LLMCardGenerator(BrokenLLM(), en_template), FakeExporter(), workdir=tmp_path)
    with pytest.raises(TemplateMismatchError):
        pipeline.run([WordInput(word="close")])
