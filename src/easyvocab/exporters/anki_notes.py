"""Card → Anki note: field values, tags, stable ids. Shared by both Anki exporters."""

import hashlib
import html
from types import ModuleType
from typing import Any

from easyvocab._jsonpath import render, resolve, to_text
from easyvocab.errors import TemplateError
from easyvocab.models import Card
from easyvocab.templates import AnkiConfig, DeckTemplate
from easyvocab.templates.config import AUDIO_PREFIX


def stable_id(name: str) -> int:
    """Deterministic 31-bit id, so re-imports hit the same note type / deck."""
    return int(hashlib.sha1(name.encode(), usedforsecurity=False).hexdigest()[:8], 16) >> 1


def anki_config(template: DeckTemplate) -> AnkiConfig:
    """The template's Anki section, or a `TemplateError` if it has none."""
    if template.config.anki is None:
        raise TemplateError(f"Template {template.name!r} has no `anki` section, so it can't be exported to Anki")
    return template.config.anki


class AnkiNoteBuilder:
    """Builds genanki notes for one template; re-imports update notes instead of duplicating them."""

    def __init__(self, template: DeckTemplate, genanki: ModuleType) -> None:
        self.template = template
        self.config = anki_config(template)
        self._genanki = genanki
        self.note_type = self._build_note_type()

    def note(self, card: Card) -> Any:
        """A genanki.Note for one card."""
        return self._genanki.Note(
            model=self.note_type,
            fields=field_values(self.config, card),
            tags=note_tags(self.config, card),
            guid=self._genanki.guid_for(self.template.name, card.word.word),
        )

    def _build_note_type(self) -> Any:
        card_types = [
            {
                "name": card_type.name,
                "qfmt": self.template.anki_file(card_type.front),
                "afmt": self.template.anki_file(card_type.back),
            }
            for card_type in self.config.card_types
        ]
        return self._genanki.Model(
            stable_id(self.config.note_type),
            self.config.note_type,
            fields=[{"name": name} for name in self.config.fields],
            templates=card_types,
            css=self.template.anki_file(self.config.css),
        )


def field_values(config: AnkiConfig, card: Card) -> list[str]:
    """Note field values in note-type order (HTML-escaped; audio fields as `[sound:...]`)."""
    return [_field_value(expression, card) for expression in config.fields.values()]


def note_tags(config: AnkiConfig, card: Card) -> list[str]:
    """Static tags + tags from field values + flag tags (spaces become underscores)."""
    tags = [*config.tags, *(to_text(resolve(path, card.fields)) for path in config.tags_from)]
    tags += [tag for path, tag in config.flag_tags.items() if resolve(path, card.fields) is True]
    return list(dict.fromkeys(tag.replace(" ", "_") for tag in tags if tag))


def _field_value(expression: str, card: Card) -> str:
    if expression.startswith(AUDIO_PREFIX):
        file_name = card.audio.get(expression.removeprefix(AUDIO_PREFIX))
        return f"[sound:{file_name}]" if file_name else ""
    return html.escape(render(expression, card.fields), quote=False)
