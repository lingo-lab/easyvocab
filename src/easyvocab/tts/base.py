"""The text-to-speech interface."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class TTS(Protocol):
    """Turns text into MP3 audio."""

    @property
    def fingerprint(self) -> str:
        """Stable id of the voice/settings; part of audio file names, so changing it re-voices."""
        ...

    def synthesize(self, text: str, lang: str) -> bytes:
        """MP3 bytes for `text`. Raise `RateLimitedError` on quota, `TTSError` on other failures."""
        ...

    def preflight(self, lang: str) -> None:
        """Raise an `EasyVocabError` if synthesis can't work now (quota hit, unknown language)."""
        ...
