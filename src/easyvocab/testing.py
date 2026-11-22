"""In-memory fakes for tests: no network, no Anki, deterministic output.

Example:
    ```python
    llm = FakeLLM([{"word": "Haus", ...}])
    card = LLMCardGenerator(llm, template).generate(WordInput(word="Haus"))
    assert len(llm.calls) == 1
    ```
"""

import threading
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from easyvocab.errors import RateLimitedError
from easyvocab.exporters.base import ExportResult
from easyvocab.models import Card, Completion, Message, Usage
from easyvocab.templates import DeckTemplate
from easyvocab.templates.deck_template import as_json_block

Reply = str | dict[str, Any]
ReplyFunction = Callable[[Sequence[Message]], Reply]
DEFAULT_USAGE = Usage(prompt_tokens=100, completion_tokens=50)


class FakeLLM:
    """Returns scripted replies (dicts are sent as ```json blocks) and records every call.

    Pass `replies` (used in order) or `respond(messages) -> reply` for input-dependent answers.
    """

    def __init__(
        self,
        replies: Iterable[Reply] = (),
        *,
        respond: ReplyFunction | None = None,
        model: str = "fake-model",
        usage: Usage = DEFAULT_USAGE,
        cost_usd: float | None = 0.001,
    ) -> None:
        self._function = respond
        self._queue: deque[Reply] = deque(replies)
        self._model = model
        self.usage = usage
        self.cost_usd = cost_usd
        self.calls: list[list[Message]] = []
        self.preflight_calls = 0
        self._lock = threading.Lock()

    @property
    def model(self) -> str:
        """Fake model name."""
        return self._model

    @property
    def fingerprint(self) -> str:
        """Model name (fakes with the same name share cache entries)."""
        return f"fake:{self._model}"

    def complete(self, messages: Sequence[Message]) -> Completion:
        """Next scripted reply."""
        with self._lock:
            self.calls.append(list(messages))
            reply = self._function(messages) if self._function else self._queue.popleft()
        text = reply if isinstance(reply, str) else as_json_block(reply)
        return Completion(text=text, model=self._model, usage=self.usage, latency_s=0.0, cost_usd=self.cost_usd)

    def preflight(self) -> None:
        """Always passes."""
        self.preflight_calls += 1


class FakeTTS:
    """Returns small fake MP3 bytes; optionally rate-limits after `limit` clips."""

    fingerprint = "fake-tts"

    def __init__(self, *, limit: int | None = None) -> None:
        self.limit = limit
        self.texts: list[str] = []

    def synthesize(self, text: str, lang: str) -> bytes:
        """Fake audio, or `RateLimitedError` once the limit is reached."""
        if self.limit is not None and len(self.texts) >= self.limit:
            raise RateLimitedError("Fake TTS")
        self.texts.append(text)
        return f"ID3 fake mp3 [{lang}] {text}".encode()

    def preflight(self, lang: str) -> None:
        """Always passes."""


class FakeExporter:
    """Keeps exported cards in memory."""

    def __init__(self) -> None:
        self.cards: list[Card] = []
        self.media_dir: Path | None = None

    def export(self, cards: Sequence[Card], template: DeckTemplate, media_dir: Path) -> ExportResult:
        """Remember the cards."""
        self.cards = list(cards)
        self.media_dir = media_dir
        return ExportResult(notes=len(self.cards), destination="memory")

    def preflight(self, template: DeckTemplate) -> None:
        """Always passes."""
