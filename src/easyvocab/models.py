"""Data passed between components: inputs, LLM messages/completions and generated cards."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["system", "user", "assistant"]


class WordInput(BaseModel):
    """One word to make a card for (the word-saver app writes exactly this format).

    Extra keys are kept and can be used by templates as input variables.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    schema_version: Literal[1] = 1
    word: str = Field(min_length=1)
    context: str = ""
    lang: str | None = None

    @field_validator("word", "context")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())

    def variables(self) -> dict[str, Any]:
        """All fields (including extra keys) as template variables."""
        return self.model_dump(exclude={"schema_version"})


@dataclass(frozen=True)
class Message:
    """One chat message."""

    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    """Token usage of one or more LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens + other.cached_prompt_tokens,
        )


@dataclass(frozen=True)
class Pricing:
    """Model prices in USD per million tokens."""

    input_per_million: float
    output_per_million: float
    cached_input_per_million: float | None = None

    def cost(self, usage: Usage) -> float:
        """Cost in USD of the given usage."""
        cached_price = self.cached_input_per_million
        if cached_price is None:
            cached_price = self.input_per_million
        uncached = usage.prompt_tokens - usage.cached_prompt_tokens
        total = uncached * self.input_per_million
        total += usage.cached_prompt_tokens * cached_price
        total += usage.completion_tokens * self.output_per_million
        return total / 1_000_000


@dataclass(frozen=True)
class Completion:
    """An LLM response with the metadata research needs (usage, cost, latency)."""

    text: str
    model: str
    usage: Usage
    latency_s: float
    cost_usd: float | None = None
    finish_reason: str | None = None


class Card(BaseModel):
    """A generated card: the template's output fields plus generation metadata."""

    model_config = ConfigDict(frozen=True)

    word: WordInput
    fields: dict[str, Any]
    template: str
    template_fingerprint: str
    generator: str
    model: str = ""
    attempts: int = 1
    usage: Usage = Usage()
    cost_usd: float | None = None
    latency_s: float = 0.0
    audio: dict[str, str] = Field(default_factory=dict)
    """Anki audio field name → media file name (filled by the audio stage)."""
