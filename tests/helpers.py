import copy
from collections.abc import Sequence
from typing import Any

from easyvocab.models import Message


def de_output(word: str = "Haus") -> dict[str, Any]:
    """A valid de-en-a1b1 card for a noun."""
    return {
        "word": word,
        "lemma": word,
        "pos": "noun",
        "article": "das",
        "plural": "die Häuser",
        "genitive": "des Hauses",
        "praesens_3sg": "",
        "praeteritum": "",
        "partizip_2": "",
        "auxiliary": "",
        "perfekt": "",
        "separable": False,
        "reflexive": False,
        "comparative": "",
        "superlative": "",
        "word_en": "house",
        "definition_de": "ein Gebäude, in dem Menschen wohnen",
        "definition_en": "a building people live in",
        "examples": [
            {"de": f"Wir haben ein {word} gekauft.", "en": "We bought a house."},
            {"de": f"Das {word} ist alt.", "en": "The house is old."},
        ],
        "tts_text": f"das {word}",
    }


def word_from_messages(messages: Sequence[Message]) -> str:
    """The word in the last user message (`Haus (hint: capitalized)` → `Haus`)."""
    return messages[-1].content.split(" (")[0]


def deep(data: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(data)
