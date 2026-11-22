import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from easyvocab import AnkiConnectExporter, AnkiPackageExporter, DeckTemplate, WordInput
from easyvocab.errors import AnkiConnectUnavailableError, EasyVocabError, TemplateError
from easyvocab.exporters.anki_connect import DEFAULT_URL, AnkiConnectClient
from easyvocab.exporters.anki_notes import field_values, note_tags
from easyvocab.models import Card
from helpers import de_output


def make_card(template: DeckTemplate, fields: dict[str, Any], audio: dict[str, str] | None = None) -> Card:
    return Card(
        word=WordInput(word=fields.get("word", "x")),
        fields=fields,
        template=template.name,
        template_fingerprint=template.fingerprint,
        generator="test",
        audio=audio or {},
    )


def test_field_values_follow_the_template(de_template: DeckTemplate) -> None:
    fields = {**de_output(), "separable": True, "definition_en": "a <big> house"}
    card = make_card(de_template, fields, audio={"word": "w.mp3"})
    assert de_template.config.anki is not None
    values = dict(zip(de_template.config.anki.fields, field_values(de_template.config.anki, card), strict=True))
    assert values["word_de"] == "Haus"
    assert values["headword"] == "das Haus"
    assert values["word_audio"] == "[sound:w.mp3]"
    assert values["example1_audio"] == ""
    assert values["example2_de"] == "Das Haus ist alt."
    assert values["separable"] == "yes"
    assert values["reflexive"] == ""
    assert values["definition_en"] == "a &lt;big&gt; house"
    assert note_tags(de_template.config.anki, card) == ["german", "noun", "trennbar"]


def test_package_contains_notes_and_media(de_template: DeckTemplate, tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "w.mp3").write_bytes(b"ID3")
    cards = [make_card(de_template, de_output("Haus"), {"word": "w.mp3", "example1": "missing.mp3"})]
    cards.append(make_card(de_template, de_output("Baum")))
    result = AnkiPackageExporter(tmp_path / "out" / "deck.apkg", "German::Test").export(cards, de_template, media)
    assert (result.notes, result.media_files) == (2, 1)
    with zipfile.ZipFile(tmp_path / "out" / "deck.apkg") as package:
        assert json.loads(package.read("media")) == {"0": "w.mp3"}
        package.extract("collection.anki2", tmp_path)
    with sqlite3.connect(tmp_path / "collection.anki2") as db:
        rows = db.execute("SELECT guid, flds, tags FROM notes ORDER BY sfld").fetchall()
    assert [row[1].split("\x1f")[0] for row in rows] == ["Baum", "Haus"]
    assert "german" in rows[0][2]


def test_guids_are_stable_across_exports(de_template: DeckTemplate, tmp_path: Path) -> None:
    def guid() -> str:
        path = tmp_path / "d.apkg"
        AnkiPackageExporter(path, "D").export([make_card(de_template, de_output())], de_template, tmp_path)
        with zipfile.ZipFile(path) as package:
            package.extract("collection.anki2", tmp_path / "x")
        with sqlite3.connect(tmp_path / "x" / "collection.anki2") as db:
            return db.execute("SELECT guid FROM notes").fetchone()[0]

    assert guid() == guid()


def test_two_card_types_for_en_ru(en_template: DeckTemplate, tmp_path: Path) -> None:
    card = make_card(
        en_template, {"word": "close", "definition": "d", "example": "e", "word_ru": "р", "example_ru": "п"}
    )
    AnkiPackageExporter(tmp_path / "en.apkg", "EN").export([card], en_template, tmp_path)
    with zipfile.ZipFile(tmp_path / "en.apkg") as package:
        package.extract("collection.anki2", tmp_path)
    with sqlite3.connect(tmp_path / "collection.anki2") as db:
        assert db.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 2


def test_template_without_anki_section(tmp_path: Path, de_template: DeckTemplate) -> None:
    de_template.config.anki = None
    with pytest.raises(TemplateError, match="no `anki` section"):
        AnkiPackageExporter(tmp_path / "x.apkg", "D").preflight(de_template)


@respx.mock
def test_anki_connect_imports_a_package(de_template: DeckTemplate, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if payload["action"] == "importPackage":
            assert Path(payload["params"]["path"]).is_file()
        return httpx.Response(200, json={"result": True if payload["action"] != "version" else 6, "error": None})

    respx.post(DEFAULT_URL).mock(side_effect=answer)
    exporter = AnkiConnectExporter("German", launch=False)
    exporter.preflight(de_template)
    result = exporter.export([make_card(de_template, de_output())], de_template, tmp_path)
    assert result.destination == "Anki: German"
    assert [call["action"] for call in calls] == ["version", "version", "importPackage"]


@respx.mock
def test_anki_connect_errors() -> None:
    client = AnkiConnectClient()
    respx.post(DEFAULT_URL).mock(side_effect=httpx.ConnectError("refused"))
    assert not client.is_available()
    with pytest.raises(AnkiConnectUnavailableError, match="2055492159"):
        client.ensure_running(launch=False)
    respx.post(DEFAULT_URL).mock(return_value=httpx.Response(200, json={"result": None, "error": "deck missing"}))
    with pytest.raises(EasyVocabError, match="deck missing"):
        client.invoke("addNotes")
