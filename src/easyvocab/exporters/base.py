"""The deck exporter interface."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from easyvocab.models import Card
from easyvocab.templates import DeckTemplate


@dataclass(frozen=True)
class ExportResult:
    """What an exporter wrote."""

    notes: int
    media_files: int = 0
    path: Path | None = None
    destination: str = ""


@runtime_checkable
class DeckExporter(Protocol):
    """Writes cards somewhere: an .apkg file, a running Anki, a CSV, ..."""

    def export(self, cards: Sequence[Card], template: DeckTemplate, media_dir: Path) -> ExportResult:
        """Export cards; audio files referenced by `card.audio` live in `media_dir`."""
        ...

    def preflight(self, template: DeckTemplate) -> None:
        """Raise an `EasyVocabError` if exporting can't work (no Anki layout, Anki closed, ...)."""
        ...
