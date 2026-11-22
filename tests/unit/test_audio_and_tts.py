from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from easyvocab import GTTS, BatchGenerator, DeckTemplate, LLMCardGenerator, WordInput
from easyvocab.errors import ConfigurationError, RateLimitedError, TTSError
from easyvocab.models import Card
from easyvocab.pipeline import AudioStage
from easyvocab.testing import FakeLLM, FakeTTS
from helpers import de_output


@pytest.fixture
def cards(generator: LLMCardGenerator, words: list[WordInput]) -> list[Card]:
    return BatchGenerator(generator).run(words).cards


def test_voices_every_audio_field_once(cards: list[Card], de_template: DeckTemplate, tmp_path: Path) -> None:
    tts = FakeTTS()
    result = AudioStage(tts, tmp_path).run(cards, de_template)
    assert len(tts.texts) == len(set(tts.texts)) == 9  # 3 words x (word + 2 examples)
    assert result.missing == 0
    assert set(result.cards[0].audio) == {"word", "example1", "example2"}
    assert all((tmp_path / name).is_file() for name in result.cards[0].audio.values())
    assert not list(tmp_path.glob(".*.part"))

    again = FakeTTS()
    AudioStage(again, tmp_path).run(cards, de_template)
    assert again.texts == []  # existing files are reused


def test_rate_limit_stops_cleanly(cards: list[Card], de_template: DeckTemplate, tmp_path: Path) -> None:
    result = AudioStage(FakeTTS(limit=4), tmp_path).run(cards, de_template)
    assert result.rate_limited
    assert result.missing == 5
    assert sum(len(card.audio) for card in result.cards) == 4


def test_shared_texts_are_voiced_once(de_template: DeckTemplate, tmp_path: Path) -> None:
    generator = LLMCardGenerator(FakeLLM([de_output("Haus"), de_output("Haus")]), de_template)
    cards = BatchGenerator(generator).run([WordInput(word="Haus"), WordInput(word="Haus", context="other")]).cards
    tts = FakeTTS()
    result = AudioStage(tts, tmp_path).run(cards, de_template)
    assert len(tts.texts) == 3
    assert result.cards[0].audio == result.cards[1].audio


def test_file_names_are_deterministic(tmp_path: Path) -> None:
    stage = AudioStage(FakeTTS(), tmp_path)
    assert stage.file_name("das Haus", "de") == stage.file_name("das Haus", "de")
    assert stage.file_name("das Haus", "de") != stage.file_name("das Haus", "en")
    assert stage.file_name("x", "de").startswith("easyvocab-de-")


class FakeGTTSModule:
    """Stands in for the `gtts` package."""

    class gTTSError(Exception):  # noqa: N801
        def __init__(self, status: int | None) -> None:
            super().__init__(f"status {status}")
            self.rsp = SimpleNamespace(status_code=status) if status else None

    def __init__(self, failures: list[Any]) -> None:
        self.failures = failures
        self.calls = 0

    def gTTS(self, text: str, **kwargs: Any) -> Any:  # noqa: N802
        module = self

        class Speaker:
            def write_to_fp(self, buffer: Any) -> None:
                module.calls += 1
                if module.failures:
                    failure = module.failures.pop(0)
                    raise failure if isinstance(failure, Exception) else module.gTTSError(failure)
                buffer.write(b"mp3:" + text.encode())

        return Speaker()


def make_gtts(failures: list[Any]) -> tuple[GTTS, FakeGTTSModule]:
    tts = GTTS(wait_seconds=0)
    fake = FakeGTTSModule(failures)
    tts._gtts = fake  # ty: ignore[invalid-assignment]
    return tts, fake


def test_gtts_success_and_transient_retry() -> None:
    tts, fake = make_gtts([500])
    assert tts.synthesize("Hallo", "de") == b"mp3:Hallo"
    assert fake.calls == 2
    assert tts.fingerprint == "gtts-com"


def test_gtts_rate_limit_is_not_retried() -> None:
    tts, fake = make_gtts([429, 429, 429])
    with pytest.raises(RateLimitedError, match="Google TTS"):
        tts.synthesize("Hallo", "de")
    assert fake.calls == 1


def test_gtts_gives_up_and_maps_language_errors() -> None:
    tts, _ = make_gtts([500, 500, 500])
    with pytest.raises(TTSError):
        tts.synthesize("Hallo", "de")
    tts, _ = make_gtts([ValueError("Language not supported: xx")])
    with pytest.raises(ConfigurationError, match="language"):
        tts.preflight("xx")
