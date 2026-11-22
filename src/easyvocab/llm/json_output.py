"""Pull a JSON object out of a model reply (```json fences, stray prose around it)."""

import json
import re
from typing import Any

from easyvocab.errors import CardValidationError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in `text`: a fenced block if present, else the outermost `{...}`."""
    candidate = _fenced(text) or _braced(text)
    if candidate is None:
        raise CardValidationError("The reply contains no JSON object")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise CardValidationError(f"The reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CardValidationError(f"Expected a JSON object, got {type(data).__name__}")
    return data


def _fenced(text: str) -> str | None:
    match = _FENCE.search(text)
    return match.group(1).strip() if match else None


def _braced(text: str) -> str | None:
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else None
