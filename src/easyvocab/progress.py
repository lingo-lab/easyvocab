"""Progress reporting hook (the library logs; UIs like a CLI pass their own callback)."""

import logging
from collections.abc import Callable

logger = logging.getLogger("easyvocab.progress")

ProgressCallback = Callable[[str, int, int], None]
"""Called as `callback(stage, done, total)` after each item, e.g. `("generate", 12, 100)`."""


def log_progress(stage: str, done: int, total: int) -> None:
    """Default callback: debug-log every item, info-log when a stage finishes."""
    level = logging.INFO if done == total else logging.DEBUG
    logger.log(level, "[%s] %d/%d", stage, done, total)
