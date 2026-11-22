"""Schema of `template.yaml`."""

import string
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

AUDIO_PREFIX = "audio:"
DERIVED_VARS = frozenset({"spelling"})
_FORMATTER = string.Formatter()


class AnkiCardType(BaseModel):
    """One Anki card type (template) of the note type."""

    model_config = ConfigDict(extra="forbid")

    name: str
    front: str = "front.html"
    back: str = "back.html"


class AnkiConfig(BaseModel):
    """How a card becomes an Anki note.

    `fields` maps Anki field name → value expression:
    a dotted path (`examples.0.de`), a format string (`{article} {lemma}`),
    or `audio:<name>` for a `[sound:...]` field. The first field is Anki's sort field.
    """

    model_config = ConfigDict(extra="forbid")

    note_type: str
    fields: dict[str, str] = Field(min_length=1)
    card_types: list[AnkiCardType] = Field(default_factory=lambda: [AnkiCardType(name="Card 1")], min_length=1)
    css: str = "style.css"
    tags: list[str] = Field(default_factory=list)
    tags_from: list[str] = Field(default_factory=list)
    """Paths whose values become tags (e.g. `pos` → `noun`)."""
    flag_tags: dict[str, str] = Field(default_factory=dict)
    """Boolean path → tag added when true (e.g. `separable: trennbar`)."""

    def audio_refs(self) -> dict[str, str]:
        """Anki field → audio name, for `audio:<name>` fields."""
        return {
            field: expression.removeprefix(AUDIO_PREFIX)
            for field, expression in self.fields.items()
            if expression.startswith(AUDIO_PREFIX)
        }


class TemplateConfig(BaseModel):
    """Everything in `template.yaml`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: str = "1"
    description: str = ""
    language: str = Field(min_length=2)
    """Language of the words being learned; used for TTS (`de`, `en`, ...)."""
    input_vars: list[str] = Field(default_factory=lambda: ["word"])
    input_format: str = "{word}"
    """User message for one word, e.g. `{word} (hint: {spelling})`."""
    audio: dict[str, str] = Field(default_factory=dict)
    """Audio name → path of the text to speak (e.g. `word: tts_text`)."""
    anki: AnkiConfig | None = None

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        unknown_vars = format_fields(self.input_format) - set(self.input_vars) - DERIVED_VARS
        if unknown_vars:
            raise ValueError(f"input_format uses {sorted(unknown_vars)}, which are not in input_vars")
        missing_audio = set(self.anki.audio_refs().values()) - set(self.audio) if self.anki else set()
        if missing_audio:
            raise ValueError(f"anki.fields reference audio {sorted(missing_audio)}, which is not defined in `audio`")
        return self


def format_fields(text: str) -> set[str]:
    """Top-level variable names used in a format string (`{a} {b.c}` → {a, b})."""
    return {field.split(".")[0].split("[")[0] for _, field, _, _ in _FORMATTER.parse(text) if field}
