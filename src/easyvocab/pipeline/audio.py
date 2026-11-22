"""Voice the template's audio fields; identical texts share one file, existing files are reused."""

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from easyvocab._jsonpath import resolve, to_text
from easyvocab.errors import RateLimitedError, TTSError
from easyvocab.models import Card
from easyvocab.progress import ProgressCallback, log_progress
from easyvocab.templates import DeckTemplate
from easyvocab.tts.base import TTS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioResult:
    """Cards with `audio` filled in, plus what's still missing."""

    cards: list[Card]
    missing: int = 0
    rate_limited: bool = False


class AudioStage:
    """Synthesize audio for every card into `media_dir`.

    File names are a hash of (voice, language, text), so re-runs and other decks reuse files.
    On `RateLimitedError` the stage stops, keeps what it has and reports `rate_limited=True`.
    """

    def __init__(self, tts: TTS, media_dir: Path, *, progress: ProgressCallback = log_progress) -> None:
        self.tts = tts
        self.media_dir = media_dir
        self.progress = progress

    def run(self, cards: Sequence[Card], template: DeckTemplate) -> AudioResult:
        """Voice what's missing and attach file names to the cards."""
        self.media_dir.mkdir(parents=True, exist_ok=True)
        texts = self._texts(cards, template)
        todo = sorted({file_name: text for file_name, text in texts.values() if not self._exists(file_name)}.items())
        rate_limited = self._synthesize_all(todo, template.language)
        voiced = [self._attach(index, card, texts) for index, card in enumerate(cards)]
        missing = sum(not self._exists(file_name) for file_name, _ in texts.values())
        return AudioResult(cards=voiced, missing=missing, rate_limited=rate_limited)

    def file_name(self, text: str, lang: str) -> str:
        """Deterministic media file name for one text."""
        digest = hashlib.sha1(f"{self.tts.fingerprint}|{lang}|{text}".encode(), usedforsecurity=False).hexdigest()
        return f"easyvocab-{lang}-{digest[:16]}.mp3"

    def _texts(self, cards: Sequence[Card], template: DeckTemplate) -> dict[tuple[int, str], tuple[str, str]]:
        """(card index, audio name) → (file name, text), for audio fields that have text."""
        texts = {}
        for index, card in enumerate(cards):
            for name, path in template.config.audio.items():
                if text := to_text(resolve(path, card.fields)).strip():
                    texts[index, name] = (self.file_name(text, template.language), text)
        return texts

    def _synthesize_all(self, todo: Sequence[tuple[str, str]], lang: str) -> bool:
        for done, (file_name, text) in enumerate(todo, start=1):
            try:
                self._write(file_name, self.tts.synthesize(text, lang))
            except RateLimitedError as exc:
                logger.warning("%s (%d clips still missing)", exc, len(todo) - done + 1)
                return True
            except TTSError as exc:
                logger.warning("No audio for %r: %s", text, exc)
            self.progress("audio", done, len(todo))
        return False

    def _attach(self, index: int, card: Card, texts: dict[tuple[int, str], tuple[str, str]]) -> Card:
        audio = {
            name: file_name
            for (card_index, name), (file_name, _) in texts.items()
            if card_index == index and self._exists(file_name)
        }
        return card.model_copy(update={"audio": {**card.audio, **audio}})

    def _write(self, file_name: str, data: bytes) -> None:
        partial = self.media_dir / f".{file_name}.part"
        partial.write_bytes(data)
        partial.replace(self.media_dir / file_name)

    def _exists(self, file_name: str) -> bool:
        return (self.media_dir / file_name).is_file()
