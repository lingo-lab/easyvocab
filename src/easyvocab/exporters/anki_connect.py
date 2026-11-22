"""Add cards straight to a running Anki through the AnkiConnect add-on."""

import logging
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from easyvocab._optional import require
from easyvocab.errors import AnkiConnectUnavailableError, EasyVocabError
from easyvocab.exporters.anki_package import AnkiPackageExporter
from easyvocab.exporters.base import ExportResult
from easyvocab.models import Card
from easyvocab.templates import DeckTemplate

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:8765"
API_VERSION = 6
IMPORT_TIMEOUT_S = 600.0


class AnkiConnectClient:
    """Minimal AnkiConnect JSON-RPC client."""

    def __init__(self, url: str = DEFAULT_URL, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def invoke(self, action: str, *, timeout: float | None = None, **params: Any) -> Any:
        """Call one AnkiConnect action and return its result."""
        payload = {"action": action, "version": API_VERSION, "params": params}
        try:
            response = httpx.post(self.url, json=payload, timeout=timeout or self.timeout)
            response.raise_for_status()
            reply = response.json()
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            raise AnkiConnectUnavailableError(self.url) from exc
        if reply.get("error"):
            raise EasyVocabError(f"AnkiConnect '{action}' failed: {reply['error']}")
        return reply.get("result")

    def is_available(self) -> bool:
        """True if AnkiConnect answers."""
        try:
            self.invoke("version", timeout=2.0)
        except AnkiConnectUnavailableError:
            return False
        return True

    def ensure_running(self, *, launch: bool, wait_s: float = 60.0, poll_s: float = 2.0) -> None:
        """Make sure Anki is up; on macOS optionally start it and wait for AnkiConnect."""
        if self.is_available():
            return
        if not (launch and sys.platform == "darwin"):
            raise AnkiConnectUnavailableError(self.url)
        logger.info("AnkiConnect isn't answering, starting Anki...")
        subprocess.Popen(["/usr/bin/open", "-a", "Anki"])
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            time.sleep(poll_s)
            if self.is_available():
                return
        raise AnkiConnectUnavailableError(self.url)


class AnkiConnectExporter:
    """Export into a running Anki (`pip install "easyvocab[anki]"` + the AnkiConnect add-on).

    Builds an .apkg in a temp folder and imports it, so the note type, notes and audio
    arrive exactly as with `AnkiPackageExporter`; re-runs update existing notes.
    """

    def __init__(self, deck_name: str, *, url: str = DEFAULT_URL, launch: bool = True) -> None:
        self.deck_name = deck_name
        self.client = AnkiConnectClient(url)
        self.launch = launch
        require("genanki", "anki")

    def preflight(self, template: DeckTemplate) -> None:
        """The template can be exported and Anki is reachable (started on macOS if needed)."""
        AnkiPackageExporter(Path(tempfile.gettempdir()) / "easyvocab.apkg", self.deck_name).preflight(template)
        self.client.ensure_running(launch=self.launch)

    def export(self, cards: Sequence[Card], template: DeckTemplate, media_dir: Path) -> ExportResult:
        """Import all cards (and audio) into the deck."""
        self.client.ensure_running(launch=self.launch)
        with tempfile.TemporaryDirectory(prefix="easyvocab-") as folder:
            package = AnkiPackageExporter(Path(folder) / "deck.apkg", self.deck_name)
            result = package.export(cards, template, media_dir)
            self.client.invoke("importPackage", path=str(package.path), timeout=IMPORT_TIMEOUT_S)
        logger.info("Imported %d notes into Anki deck %r", result.notes, self.deck_name)
        return ExportResult(notes=result.notes, media_files=result.media_files, destination=f"Anki: {self.deck_name}")
