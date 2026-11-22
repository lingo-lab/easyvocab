"""The card generator interface: one word in, one validated card out."""

from typing import Protocol, runtime_checkable

from easyvocab.models import Card, WordInput
from easyvocab.templates import DeckTemplate


@runtime_checkable
class CardGenerator(Protocol):
    """Turns a `WordInput` into a `Card` that matches `template`'s output schema."""

    @property
    def template(self) -> DeckTemplate:
        """The deck template cards are generated for."""
        ...

    @property
    def fingerprint(self) -> str:
        """Stable hash of everything that changes the output; used in cache keys."""
        ...

    def generate(self, word: WordInput) -> Card:
        """Generate one card. Raise `GenerationError` for a per-word failure."""
        ...

    def preflight(self) -> None:
        """Raise an `EasyVocabError` if generation can't work at all."""
        ...
