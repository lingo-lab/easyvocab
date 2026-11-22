"""Tiny dotted-path lookup used by templates: `examples.0.de`, or format strings like `{article} {lemma}`."""

import string
from collections.abc import Mapping
from typing import Any

_FORMATTER = string.Formatter()


def resolve(path: str, data: Any) -> Any:
    """Value at a dotted path (`examples.0.de`); None if any step is missing."""
    current = data
    for part in path.split("."):
        current = _step(current, part)
        if current is None:
            return None
    return current


def render(expression: str, data: Mapping[str, Any]) -> str:
    """Render a path (`lemma`) or a format string (`{article} {lemma}`) as display text."""
    if "{" not in expression:
        return to_text(resolve(expression, data))
    parts = [
        literal + (to_text(resolve(field, data)) if field else "")
        for literal, field, _, _ in _FORMATTER.parse(expression)
    ]
    return " ".join("".join(parts).split())


def to_text(value: Any) -> str:
    """Display text for a field value: bools → "yes"/"", lists → comma-separated, None → ""."""
    if value is None or value is False:
        return ""
    if value is True:
        return "yes"
    if isinstance(value, list):
        return ", ".join(to_text(item) for item in value if to_text(item))
    return str(value)


def _step(current: Any, part: str) -> Any:
    if isinstance(current, Mapping):
        return current.get(part)
    if isinstance(current, list) and part.isdigit():
        index = int(part)
        return current[index] if index < len(current) else None
    return None
