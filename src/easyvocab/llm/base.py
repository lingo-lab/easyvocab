"""The LLM interface. Implement these four members to plug in any provider."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from easyvocab.models import Completion, Message


@runtime_checkable
class LLM(Protocol):
    """A chat model that turns messages into a completion."""

    @property
    def model(self) -> str:
        """Model identifier, e.g. `accounts/fireworks/models/deepseek-v4p1-flash`."""
        ...

    @property
    def fingerprint(self) -> str:
        """Stable hash of everything that changes the output (model, params); used in cache keys."""
        ...

    def complete(self, messages: Sequence[Message]) -> Completion:
        """Run one chat completion."""
        ...

    def preflight(self) -> None:
        """Raise an `EasyVocabError` if the model can't be used (missing key, unknown model)."""
        ...
