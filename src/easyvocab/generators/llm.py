"""Single-prompt LLM generator: template messages → JSON → schema check, with fix-up retries."""

import hashlib
import logging
from collections.abc import Sequence
from typing import Any

from easyvocab.errors import CardValidationError, GenerationError, LLMError
from easyvocab.llm.base import LLM
from easyvocab.llm.json_output import extract_json
from easyvocab.models import Card, Completion, Message, Usage, WordInput
from easyvocab.templates import DeckTemplate

logger = logging.getLogger(__name__)

FIX_PROMPT = (
    "Your answer can't be used: {problem}\n"
    "Reply again with the complete, corrected JSON object only, inside a ```json code block."
)


class LLMCardGenerator:
    """Generate a card with one LLM prompt (system instruction + few-shot examples).

    If the reply isn't valid JSON or breaks the schema, the model sees its reply and the
    validation errors and gets another try, up to `max_attempts` calls in total.

    Example:
        ```python
        generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
        card = generator.generate(WordInput(word="Haus"))
        ```
    """

    kind = "llm"

    def __init__(self, llm: LLM, template: DeckTemplate, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.llm = llm
        self._template = template
        self.max_attempts = max_attempts

    @property
    def template(self) -> DeckTemplate:
        """The deck template."""
        return self._template

    @property
    def fingerprint(self) -> str:
        """Generator kind + LLM fingerprint."""
        return hashlib.sha256(f"{self.kind}|{self.llm.fingerprint}".encode()).hexdigest()[:16]

    def preflight(self) -> None:
        """Check the template's examples, then the LLM."""
        self._template.preflight()
        self.llm.preflight()

    def generate(self, word: WordInput) -> Card:
        """Generate and validate one card."""
        messages = self._template.build_messages(word)
        completions: list[Completion] = []
        problem = ""
        for _ in range(self.max_attempts):
            completion = self._complete(word, messages)
            completions.append(completion)
            try:
                return self._card(word, self._parse(completion.text), completions)
            except CardValidationError as exc:
                problem = str(exc)
                logger.info("Invalid card for %r (attempt %d): %s", word.word, len(completions), problem)
                messages = [
                    *messages,
                    Message("assistant", completion.text),
                    Message("user", FIX_PROMPT.format(problem=problem)),
                ]
        raise GenerationError(word.word, f"no valid card after {self.max_attempts} attempts ({problem})")

    def _complete(self, word: WordInput, messages: Sequence[Message]) -> Completion:
        try:
            return self.llm.complete(messages)
        except LLMError as exc:
            raise GenerationError(word.word, str(exc)) from exc

    def _parse(self, text: str) -> dict[str, Any]:
        data = extract_json(text)
        self._template.validate_output(data)
        return data

    def _card(self, word: WordInput, fields: dict[str, Any], completions: list[Completion]) -> Card:
        costs = [completion.cost_usd for completion in completions]
        return Card(
            word=word,
            fields=fields,
            template=self._template.name,
            template_fingerprint=self._template.fingerprint,
            generator=self.fingerprint,
            model=completions[-1].model,
            attempts=len(completions),
            usage=sum((completion.usage for completion in completions), Usage()),
            cost_usd=None if None in costs else sum(cost for cost in costs if cost is not None),
            latency_s=sum(completion.latency_s for completion in completions),
        )
