"""words → cards → audio → deck, with preflight checks and resumable stages."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from easyvocab.batch import BatchGenerator, BatchResult, CardCache
from easyvocab.errors import EasyVocabError, PreflightError, RateLimitedError
from easyvocab.exporters.base import DeckExporter, ExportResult
from easyvocab.generators.base import CardGenerator
from easyvocab.models import Card, WordInput
from easyvocab.pipeline.audio import AudioStage
from easyvocab.progress import ProgressCallback, log_progress
from easyvocab.tts.base import TTS

logger = logging.getLogger(__name__)

CACHE_FILE = "cache.sqlite"
MEDIA_DIR = "media"


@dataclass(frozen=True)
class PipelineResult:
    """Everything a run produced."""

    batch: BatchResult
    export: ExportResult
    missing_audio: int = 0
    audio_rate_limited: bool = False

    @property
    def cards(self) -> list[Card]:
        """Exported cards."""
        return self.batch.cards

    @property
    def failures(self) -> dict[str, str]:
        """Word → reason, for words without a card (re-run to retry them)."""
        return self.batch.failures


class Pipeline:
    """Generate cards, voice them and export the deck.

    Every stage is resumable: cards are cached in `workdir/cache.sqlite`, audio lives in
    `workdir/media/`, so re-running only does the missing work. Before any paid call,
    all components' `preflight()` checks run and every problem is reported at once.

    Example:
        ```python
        pipeline = Pipeline(generator, AnkiConnectExporter("German::A1-B1"), tts=GTTS())
        result = pipeline.run(load_inputs("words.txt"))
        ```
    """

    def __init__(
        self,
        generator: CardGenerator,
        exporter: DeckExporter,
        *,
        tts: TTS | None = None,
        workdir: str | Path = ".easyvocab",
        workers: int = 8,
        preflight: bool = True,
        progress: ProgressCallback = log_progress,
    ) -> None:
        self.generator = generator
        self.exporter = exporter
        self.tts = tts
        self.workdir = Path(workdir).expanduser()
        self.workers = workers
        self.run_preflight = preflight
        self.progress = progress

    @property
    def media_dir(self) -> Path:
        """Folder with the generated audio."""
        return self.workdir / MEDIA_DIR

    def preflight(self) -> None:
        """Run every component's check; raise one `PreflightError` listing all problems."""
        problems = [problem for check in self._checks() if (problem := _problem(check))]
        if problems:
            raise PreflightError(problems)

    def run(self, words: Iterable[WordInput]) -> PipelineResult:
        """Run all stages for `words`."""
        words = list(words)
        template = self.generator.template
        template.verify(words)
        if self.run_preflight:
            self.preflight()
        with CardCache(self.workdir / CACHE_FILE) as cache:
            batch = BatchGenerator(self.generator, cache=cache, workers=self.workers, progress=self.progress).run(words)
        cards, missing, rate_limited = self._voice(batch.cards)
        export = self.exporter.export(cards, template, self.media_dir)
        _log_summary(batch, export, missing)
        return PipelineResult(
            batch=BatchResult(cards=cards, failures=batch.failures, cached=batch.cached, generated=batch.generated),
            export=export,
            missing_audio=missing,
            audio_rate_limited=rate_limited,
        )

    def _voice(self, cards: list[Card]) -> tuple[list[Card], int, bool]:
        if self.tts is None:
            return cards, 0, False
        result = AudioStage(self.tts, self.media_dir, progress=self.progress).run(cards, self.generator.template)
        return result.cards, result.missing, result.rate_limited

    def _checks(self) -> list[Callable[[], None]]:
        template = self.generator.template
        checks = [self.generator.preflight, lambda: self.exporter.preflight(template)]
        if self.tts is not None and template.config.audio:
            checks.append(lambda: self._preflight_tts(template.language))
        return checks

    def _preflight_tts(self, lang: str) -> None:
        tts = self.tts
        if tts is None:
            return
        try:
            tts.preflight(lang)
        except RateLimitedError as exc:
            logger.warning("%s The deck is built without the missing audio for now.", exc)


def _problem(check: Callable[[], None]) -> str | None:
    try:
        check()
    except EasyVocabError as exc:
        return str(exc)
    return None


def _log_summary(batch: BatchResult, export: ExportResult, missing_audio: int) -> None:
    logger.info(
        "%d cards (%d cached, %d new, %d failed), $%.4f, %d audio clips missing → %s",
        len(batch.cards),
        batch.cached,
        batch.generated,
        len(batch.failures),
        batch.cost_usd,
        missing_audio,
        export.destination,
    )
