"""Generate cards for many words in parallel, with a resumable on-disk cache."""

import hashlib
import json
import logging
import sqlite3
from collections.abc import Iterable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Self

from easyvocab.errors import GenerationError
from easyvocab.generators.base import CardGenerator
from easyvocab.models import Card, WordInput
from easyvocab.progress import ProgressCallback, log_progress

logger = logging.getLogger(__name__)

_SCHEMA = "CREATE TABLE IF NOT EXISTS cards (key TEXT PRIMARY KEY, card TEXT NOT NULL)"


class CardCache:
    """sqlite cache of generated cards, keyed by hash(template, generator, word, context).

    Use it from one thread only (`BatchGenerator` writes from the main thread).
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = path if str(path) == ":memory:" else Path(path).expanduser()
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute(_SCHEMA)

    @staticmethod
    def key(generator: CardGenerator, word: WordInput) -> str:
        """Cache key: changes when the template, the model/params or the input changes."""
        parts = [generator.template.fingerprint, generator.fingerprint, word.word, word.context]
        return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()

    def get(self, key: str) -> Card | None:
        """Cached card or None."""
        row = self._connection.execute("SELECT card FROM cards WHERE key = ?", (key,)).fetchone()
        return Card.model_validate_json(row[0]) if row else None

    def put(self, key: str, card: Card) -> None:
        """Store (or replace) a card and commit right away, so a crash loses nothing."""
        self._connection.execute("INSERT OR REPLACE INTO cards VALUES (?, ?)", (key, card.model_dump_json()))
        self._connection.commit()

    def __len__(self) -> int:
        return self._connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]

    def close(self) -> None:
        """Close the database."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()


@dataclass(frozen=True)
class BatchResult:
    """Cards in input order (failed words are missing) plus per-word failures."""

    cards: list[Card]
    failures: dict[str, str] = field(default_factory=dict)
    cached: int = 0
    generated: int = 0

    @property
    def cost_usd(self) -> float:
        """Total known cost of all cards (cached cards count with their original cost)."""
        return sum(card.cost_usd or 0.0 for card in self.cards)


class BatchGenerator:
    """Run a `CardGenerator` over many words: cached words are skipped, the rest run in parallel.

    Per-word `GenerationError`s are collected in `BatchResult.failures` and the run goes on.
    Anything else (bad API key, rate limit) stops the run; finished cards stay cached.
    """

    def __init__(
        self,
        generator: CardGenerator,
        *,
        cache: CardCache | None = None,
        workers: int = 8,
        progress: ProgressCallback = log_progress,
    ) -> None:
        self.generator = generator
        self.cache = cache if cache is not None else CardCache()
        self.workers = workers
        self.progress = progress

    def run(self, words: Iterable[WordInput]) -> BatchResult:
        """Generate (or load from cache) one card per word."""
        words = list(words)
        self.generator.template.verify(words)
        keys = [CardCache.key(self.generator, word) for word in words]
        cards: dict[str, Card] = {key: card for key in keys if (card := self.cache.get(key))}
        pending = {key: word for key, word in zip(keys, words, strict=True) if key not in cards}
        todo = list(pending.items())
        logger.info("%d cards cached, %d to generate", len(cards), len(todo))
        cached = len(cards)
        failures = self._generate(todo, cards)
        ordered = [cards[key] for key in dict.fromkeys(keys) if key in cards]
        return BatchResult(cards=ordered, failures=failures, cached=cached, generated=len(cards) - cached)

    def _generate(self, todo: Sequence[tuple[str, WordInput]], cards: dict[str, Card]) -> dict[str, str]:
        failures: dict[str, str] = {}
        if not todo:
            return failures
        pool = ThreadPoolExecutor(max_workers=self.workers)
        futures = {pool.submit(self.generator.generate, word): (key, word) for key, word in todo}
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                self._collect(future, futures[future], cards, failures)
                self.progress("generate", done, len(todo))
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        return failures

    def _collect(
        self, future: Future[Card], item: tuple[str, WordInput], cards: dict[str, Card], failures: dict[str, str]
    ) -> None:
        key, word = item
        try:
            card = future.result()
        except GenerationError as exc:
            failures[word.word] = exc.reason
            logger.warning("%s", exc)
            return
        self.cache.put(key, card)
        cards[key] = card
