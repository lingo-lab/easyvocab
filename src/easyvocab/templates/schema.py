"""JSON Schema validation of generated cards, with errors a model (and a human) can act on."""

import json
from pathlib import Path
from typing import Any

from jsonschema import SchemaError
from jsonschema.validators import validator_for

from easyvocab.errors import CardValidationError, TemplateError

MAX_REPORTED_ERRORS = 5


class OutputSchema:
    """The template's `output_schema.json`."""

    def __init__(self, schema: dict[str, Any]) -> None:
        validator_class = validator_for(schema)
        try:
            validator_class.check_schema(schema)
        except SchemaError as exc:
            raise TemplateError(f"output_schema.json is not a valid JSON Schema: {exc.message}") from exc
        self.schema = schema
        self._validator = validator_class(schema)

    @classmethod
    def from_file(cls, path: Path) -> "OutputSchema":
        """Load a schema file."""
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise TemplateError(f"{path} is not valid JSON: {exc}") from exc

    def errors(self, data: Any) -> list[str]:
        """Human-readable validation errors (`examples/0/de: '' is too short`), empty if valid."""
        found = sorted(self._validator.iter_errors(data), key=lambda error: list(map(str, error.absolute_path)))
        return [f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in found]

    def validate(self, data: Any) -> None:
        """Raise `CardValidationError` listing (up to 5) problems."""
        if problems := self.errors(data):
            raise CardValidationError("; ".join(problems[:MAX_REPORTED_ERRORS]))
