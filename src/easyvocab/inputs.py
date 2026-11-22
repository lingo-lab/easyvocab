"""Load word lists: `.json` (list of objects), `.jsonl`, or `.txt` (one word per line)."""

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from easyvocab.errors import ConfigurationError
from easyvocab.models import WordInput


def load_inputs(path: str | Path) -> list[WordInput]:
    """Read and validate a word list; duplicates (same word + context) are dropped, order is kept."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ConfigurationError(f"Input file not found: {path}")
    rows = _read_rows(path)
    words = [_to_word(row, index, path) for index, row in enumerate(rows)]
    return dedupe(words)


def dedupe(words: Iterable[WordInput]) -> list[WordInput]:
    """Drop repeated (word, context) pairs, keeping the first occurrence."""
    unique: dict[tuple[str, str], WordInput] = {}
    for word in words:
        unique.setdefault((word.word, word.context), word)
    return list(unique.values())


def _read_rows(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    match path.suffix.lower():
        case ".json":
            return _json_list(text, path)
        case ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        case ".txt":
            return list(_txt_rows(text))
        case suffix:
            raise ConfigurationError(f"Unsupported input format '{suffix}' ({path}); use .json, .jsonl or .txt")


def _json_list(text: str, path: Path) -> list[Any]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ConfigurationError(f"{path} must contain a JSON list of word objects")
    return data


def _txt_rows(text: str) -> Iterator[dict[str, str]]:
    for line in text.splitlines():
        word = " ".join(line.split()).removesuffix("...").strip()
        if word and not word.startswith("#"):
            yield {"word": word}


def _to_word(row: Any, index: int, path: Path) -> WordInput:
    if isinstance(row, str):
        row = {"word": row}
    try:
        return WordInput.model_validate(row)
    except ValidationError as exc:
        raise ConfigurationError(f"{path}: item #{index} is not a valid word input: {exc}") from exc
