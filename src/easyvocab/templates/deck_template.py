"""A deck template: one folder with everything needed for one kind of deck."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from easyvocab.errors import TemplateError, TemplateMismatchError
from easyvocab.models import Message, WordInput
from easyvocab.templates.config import TemplateConfig
from easyvocab.templates.schema import OutputSchema

BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"
CONFIG_FILE = "template.yaml"
INSTRUCTION_FILE = "instruction.md"
EXAMPLES_FILE = "examples.json"
SCHEMA_FILE = "output_schema.json"
ANKI_DIR = "anki"
REQUIRED_FILES = (CONFIG_FILE, INSTRUCTION_FILE, EXAMPLES_FILE, SCHEMA_FILE)


@dataclass(frozen=True)
class Example:
    """One few-shot example: template input variables → expected card fields."""

    input: dict[str, Any]
    output: dict[str, Any]


class DeckTemplate:
    """Prompt, few-shot examples, output schema, Anki layout and audio settings for one deck type.

    Folder layout:

    ```
    template.yaml        name, language, input vars/format, audio, anki fields
    instruction.md       system prompt
    examples.json        [{"input": {...}, "output": {...}}, ...]
    output_schema.json   JSON Schema every generated card must match
    anki/                front.html, back.html, style.css (optional)
    ```

    Example:
        ```python
        template = DeckTemplate.builtin("de-en-a1b1")
        messages = template.build_messages(WordInput(word="Haus"))
        ```
    """

    def __init__(
        self,
        config: TemplateConfig,
        instruction: str,
        examples: list[Example],
        schema: OutputSchema,
        directory: Path | None = None,
    ) -> None:
        self.config = config
        self.instruction = instruction.strip()
        self.examples = examples
        self.schema = schema
        self.directory = directory

    @classmethod
    def from_dir(cls, path: str | Path) -> "DeckTemplate":
        """Load a template folder."""
        directory = Path(path).expanduser().resolve()
        missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
        if missing:
            raise TemplateError(f"Template folder {directory} is missing: {', '.join(missing)}")
        return cls(
            config=_load_config(directory / CONFIG_FILE),
            instruction=(directory / INSTRUCTION_FILE).read_text(encoding="utf-8"),
            examples=_load_examples(directory / EXAMPLES_FILE),
            schema=OutputSchema.from_file(directory / SCHEMA_FILE),
            directory=directory,
        )

    @classmethod
    def builtin(cls, name: str) -> "DeckTemplate":
        """Load a template shipped with easyvocab (see `list_builtin()`)."""
        if name not in cls.list_builtin():
            raise TemplateError(f"No built-in template {name!r}. Available: {', '.join(cls.list_builtin())}")
        return cls.from_dir(BUILTIN_DIR / name)

    @staticmethod
    def list_builtin() -> list[str]:
        """Names of the built-in templates."""
        return sorted(path.name for path in BUILTIN_DIR.iterdir() if (path / CONFIG_FILE).is_file())

    @property
    def name(self) -> str:
        """Template name from `template.yaml`."""
        return self.config.name

    @property
    def language(self) -> str:
        """Language of the words (used for TTS)."""
        return self.config.language

    @property
    def fingerprint(self) -> str:
        """Hash of everything that changes generation (not the Anki layout)."""
        payload = {
            "version": self.config.version,
            "input_format": self.config.input_format,
            "instruction": self.instruction,
            "examples": [(example.input, example.output) for example in self.examples],
            "schema": self.schema.schema,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

    @property
    def example_words(self) -> frozenset[str]:
        """Words used as few-shot examples (keep them out of eval sets)."""
        return frozenset(str(example.input.get("word", "")) for example in self.examples)

    def build_messages(self, word: WordInput) -> list[Message]:
        """System instruction, few-shot turns, then the word."""
        messages = [Message("system", self.instruction)]
        for example in self.examples:
            messages.append(Message("user", self.format_input(example.input)))
            messages.append(Message("assistant", as_json_block(example.output)))
        messages.append(Message("user", self.format_input(word.variables())))
        return messages

    def format_input(self, variables: dict[str, Any]) -> str:
        """Render `input_format` for one word (adds derived vars like `spelling`)."""
        word = str(variables.get("word", ""))
        return self.config.input_format.format_map({**variables, "spelling": spelling_hint(word)})

    def validate_output(self, data: dict[str, Any]) -> None:
        """Raise `CardValidationError` if `data` doesn't match the output schema."""
        self.schema.validate(data)

    def verify(self, words: Iterable[WordInput]) -> None:
        """Raise `TemplateMismatchError` if an input lacks a variable the template needs."""
        for index, word in enumerate(words):
            missing = [name for name in self.config.input_vars if name not in word.variables()]
            if missing:
                raise TemplateMismatchError(index, missing[0], word.word)

    def preflight(self) -> None:
        """Check that every few-shot example matches the schema and the input variables."""
        for index, example in enumerate(self.examples):
            if problems := self.schema.errors(example.output):
                raise TemplateError(f"{self.name}: example #{index} doesn't match the schema: {problems[0]}")
            missing = set(self.config.input_vars) - set(example.input)
            if missing:
                raise TemplateError(f"{self.name}: example #{index} input lacks {sorted(missing)}")

    def anki_file(self, name: str) -> str:
        """Contents of a file in the template's `anki/` folder."""
        path = self.directory / ANKI_DIR / name if self.directory else None
        if path is None or not path.is_file():
            raise TemplateError(f"Template {self.name!r} has no {ANKI_DIR}/{name}")
        return path.read_text(encoding="utf-8")


def spelling_hint(word: str) -> str:
    """`capitalized` / `lowercase`, prefixed with `multi-word, ` for phrases (helps German POS)."""
    case = "capitalized" if word[:1].isupper() else "lowercase"
    return f"multi-word, {case}" if " " in word.strip() else case


def as_json_block(data: dict[str, Any]) -> str:
    """Pretty JSON in a ```json fence (the format the model is asked to answer in)."""
    return f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"


def _load_config(path: Path) -> TemplateConfig:
    try:
        return TemplateConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        raise TemplateError(f"{path} is not valid YAML: {exc}") from exc
    except ValidationError as exc:
        raise TemplateError(f"{path} is invalid:\n{exc}") from exc


def _load_examples(path: Path) -> list[Example]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [Example(input=row["input"], output=row["output"]) for row in rows]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TemplateError(f"{path} must be a JSON list of {{'input': ..., 'output': ...}} objects ({exc})") from exc
