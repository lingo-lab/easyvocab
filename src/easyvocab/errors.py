"""User-facing errors. Every message says what went wrong and what to do about it."""

from collections.abc import Sequence

ANKI_CONNECT_URL = "https://ankiweb.net/shared/info/2055492159"


class EasyVocabError(Exception):
    """Base class for all easyvocab errors."""


class ConfigurationError(EasyVocabError):
    """A component is misconfigured (missing API key, unknown model, bad path)."""


class MissingExtraError(EasyVocabError):
    """An optional dependency is not installed."""

    def __init__(self, module: str, extra: str) -> None:
        super().__init__(f"'{module}' is not installed. Install it with: pip install \"easyvocab[{extra}]\"")
        self.module = module
        self.extra = extra


class PreflightError(EasyVocabError):
    """One or more components failed their preflight check."""

    def __init__(self, problems: Sequence[str]) -> None:
        bullets = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(f"Preflight failed (nothing was generated or spent):\n{bullets}")
        self.problems = list(problems)


class TemplateError(EasyVocabError):
    """A deck template folder is missing files or is invalid."""


class TemplateMismatchError(TemplateError):
    """An input item doesn't provide a variable the template needs."""

    def __init__(self, index: int, field: str, word: str) -> None:
        super().__init__(f"Input #{index} ({word!r}) has no '{field}', which the template requires")
        self.index = index
        self.field = field


class LLMError(EasyVocabError):
    """An LLM call failed (network, server error, bad request)."""


class CardValidationError(EasyVocabError):
    """A model response is not valid JSON or doesn't match the template's output schema."""


class GenerationError(EasyVocabError):
    """A card couldn't be generated for a word."""

    def __init__(self, word: str, reason: str) -> None:
        super().__init__(f"Couldn't generate a card for {word!r}: {reason}")
        self.word = word
        self.reason = reason


class TTSError(EasyVocabError):
    """Text-to-speech failed for one text (after retries)."""


class RateLimitedError(EasyVocabError):
    """A service is rate-limiting us; retry later."""

    def __init__(self, service: str, retry_after: float | None = None, hint: str = "") -> None:
        wait = f"retry in {retry_after:.0f}s" if retry_after else "wait a while and run again"
        super().__init__(f"{service} is rate-limiting requests ({wait}). {hint}".strip())
        self.service = service
        self.retry_after = retry_after


class AnkiConnectUnavailableError(EasyVocabError):
    """AnkiConnect doesn't answer: Anki is closed or the add-on is missing."""

    def __init__(self, url: str) -> None:
        super().__init__(
            f"Can't reach AnkiConnect at {url}. Start Anki and make sure the AnkiConnect add-on "
            f"(code 2055492159, {ANKI_CONNECT_URL}) is installed. "
            "Or export to a file instead with AnkiPackageExporter."
        )
        self.url = url
