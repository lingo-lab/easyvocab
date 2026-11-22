"""Free Google Translate voice via gTTS (unofficial endpoint, rate-limited after ~2000 clips)."""

import io
import logging
from typing import Any

from easyvocab._optional import require
from easyvocab.errors import ConfigurationError, RateLimitedError, TTSError

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429
QUOTA_HINT = (
    "Google TTS (gTTS) blocks a client for a few hours after roughly 2000 clips. "
    "Progress is saved: run the same command again later and only the missing audio is made."
)


class GTTS:
    """Google Translate text-to-speech (`pip install "easyvocab[tts]"`).

    Transient errors are retried with exponential backoff; HTTP 429 raises
    `RateLimitedError` immediately, since retrying only extends the block.
    """

    def __init__(
        self, *, tld: str = "com", slow: bool = False, max_attempts: int = 3, wait_seconds: float = 5.0
    ) -> None:
        self._gtts = require("gtts", "tts")
        self._tenacity = require("tenacity", "tts")
        self.tld = tld
        self.slow = slow
        self.max_attempts = max_attempts
        self.wait_seconds = wait_seconds

    @property
    def fingerprint(self) -> str:
        """Voice settings."""
        return f"gtts-{self.tld}{'-slow' if self.slow else ''}"

    def synthesize(self, text: str, lang: str) -> bytes:
        """MP3 bytes for `text`."""
        retrying = self._tenacity.Retrying(
            stop=self._tenacity.stop_after_attempt(self.max_attempts),
            wait=self._tenacity.wait_exponential(multiplier=self.wait_seconds, max=60),
            retry=self._tenacity.retry_if_exception_type(TTSError),
            reraise=True,
        )
        return retrying(self._synthesize_once, text, lang)

    def preflight(self, lang: str) -> None:
        """One tiny request: fails fast on quota or an unsupported language."""
        self._synthesize_once("Test", lang)

    def _synthesize_once(self, text: str, lang: str) -> bytes:
        buffer = io.BytesIO()
        try:
            self._gtts.gTTS(text, lang=lang, tld=self.tld, slow=self.slow).write_to_fp(buffer)
        except ValueError as exc:
            raise ConfigurationError(f"gTTS doesn't support the language {lang!r}: {exc}") from exc
        except self._gtts.gTTSError as exc:
            raise _map_error(exc) from exc
        return buffer.getvalue()


def _map_error(exc: Any) -> Exception:
    status = getattr(getattr(exc, "rsp", None), "status_code", None)
    if status == HTTP_TOO_MANY_REQUESTS:
        return RateLimitedError("Google TTS", hint=QUOTA_HINT)
    return TTSError(f"gTTS failed: {exc}")
