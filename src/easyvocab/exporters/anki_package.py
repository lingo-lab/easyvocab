"""Write an Anki package (.apkg): note type + notes + audio in one file. Anki doesn't need to run."""

import logging
from collections.abc import Sequence
from pathlib import Path

from easyvocab._optional import require
from easyvocab.errors import ConfigurationError
from easyvocab.exporters.anki_notes import AnkiNoteBuilder, anki_config, stable_id
from easyvocab.exporters.base import ExportResult
from easyvocab.models import Card
from easyvocab.templates import DeckTemplate

logger = logging.getLogger(__name__)


class AnkiPackageExporter:
    """Export to an `.apkg` file (`pip install "easyvocab[anki]"`). Import it with File → Import."""

    def __init__(self, path: str | Path, deck_name: str) -> None:
        self._genanki = require("genanki", "anki")
        self.path = Path(path).expanduser()
        self.deck_name = deck_name

    def preflight(self, template: DeckTemplate) -> None:
        """The template has an Anki layout and the output folder is writable."""
        anki_config(template)
        AnkiNoteBuilder(template, self._genanki)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError(f"Can't create the output folder {self.path.parent}: {exc}") from exc

    def export(self, cards: Sequence[Card], template: DeckTemplate, media_dir: Path) -> ExportResult:
        """Write all cards and their audio into one .apkg file."""
        builder = AnkiNoteBuilder(template, self._genanki)
        deck = self._genanki.Deck(stable_id(self.deck_name), self.deck_name)
        for card in cards:
            deck.add_note(builder.note(card))
        media = media_files(cards, media_dir)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._genanki.Package(deck, media_files=[str(path) for path in media]).write_to_file(str(self.path))
        logger.info("Wrote %d notes and %d audio files to %s", len(cards), len(media), self.path)
        return ExportResult(notes=len(cards), media_files=len(media), path=self.path, destination=str(self.path))


def media_files(cards: Sequence[Card], media_dir: Path) -> list[Path]:
    """Existing audio files referenced by the cards (deduplicated, sorted)."""
    names = {name for card in cards for name in card.audio.values()}
    return sorted(path for name in names if (path := media_dir / name).is_file())
