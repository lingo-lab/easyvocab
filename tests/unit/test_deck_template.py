import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from easyvocab import DeckTemplate, WordInput
from easyvocab.errors import CardValidationError, TemplateError, TemplateMismatchError
from easyvocab.templates.deck_template import BUILTIN_DIR, spelling_hint


@pytest.mark.parametrize("name", DeckTemplate.list_builtin())
def test_builtin_templates_are_self_consistent(name: str) -> None:
    template = DeckTemplate.builtin(name)
    template.preflight()
    assert template.config.anki is not None
    for card_type in template.config.anki.card_types:
        assert template.anki_file(card_type.front)
        assert template.anki_file(card_type.back)
    assert template.anki_file(template.config.anki.css)


def test_builtin_list_and_unknown() -> None:
    assert {"de-en-a1b1", "en-ru"} <= set(DeckTemplate.list_builtin())
    with pytest.raises(TemplateError, match="Available"):
        DeckTemplate.builtin("nope")


def test_build_messages_is_system_fewshot_then_word(de_template: DeckTemplate) -> None:
    messages = de_template.build_messages(WordInput(word="Bescheid sagen"))
    roles = [message.role for message in messages]
    assert roles == ["system", *["user", "assistant"] * len(de_template.examples), "user"]
    assert messages[1].content == "Verkehr (hint: capitalized)"
    assert messages[2].content.startswith("```json\n{")
    assert messages[-1].content == "Bescheid sagen (hint: multi-word, capitalized)"
    assert "## Examples" not in messages[0].content


def test_static_prefix_is_identical_across_words(de_template: DeckTemplate) -> None:
    first = de_template.build_messages(WordInput(word="a"))
    second = de_template.build_messages(WordInput(word="b"))
    assert first[:-1] == second[:-1]


@pytest.mark.parametrize(
    ("word", "hint"),
    [("Haus", "capitalized"), ("gehen", "lowercase"), ("Rad fahren", "multi-word, capitalized")],
)
def test_spelling_hint(word: str, hint: str) -> None:
    assert spelling_hint(word) == hint


def test_validate_output(de_template: DeckTemplate, valid_output: dict[str, Any]) -> None:
    de_template.validate_output(valid_output)
    broken = {**valid_output, "pos": "noun", "article": "", "examples": []}
    with pytest.raises(CardValidationError) as error:
        de_template.validate_output(broken)
    assert "examples" in str(error.value)
    assert "article" in str(error.value)


def test_verify_reports_missing_input_vars(en_template: DeckTemplate) -> None:
    en_template.verify([WordInput(word="close")])  # context defaults to ""
    template = DeckTemplate.builtin("en-ru")
    template.config.input_vars.append("level")
    with pytest.raises(TemplateMismatchError, match="level"):
        template.verify([WordInput(word="close")])


def test_fingerprint_ignores_anki_layout_but_not_prompt(tmp_path: Path) -> None:
    folder = tmp_path / "tpl"
    shutil.copytree(BUILTIN_DIR / "de-en-a1b1", folder)
    original = DeckTemplate.from_dir(folder).fingerprint
    (folder / "anki" / "style.css").write_text("/* new look */", encoding="utf-8")
    assert DeckTemplate.from_dir(folder).fingerprint == original
    (folder / "instruction.md").write_text("Be brief.", encoding="utf-8")
    assert DeckTemplate.from_dir(folder).fingerprint != original


def _custom_template(folder: Path, **overrides: Any) -> Path:
    folder.mkdir()
    config = {"name": "tiny", "language": "en", "input_format": "{word}", **overrides}
    (folder / "template.yaml").write_text(json.dumps(config), encoding="utf-8")
    (folder / "instruction.md").write_text("Translate.", encoding="utf-8")
    (folder / "examples.json").write_text('[{"input": {"word": "cat"}, "output": {"t": "Katze"}}]', encoding="utf-8")
    schema = {"type": "object", "required": ["t"], "properties": {"t": {"type": "string"}}}
    (folder / "output_schema.json").write_text(json.dumps(schema), encoding="utf-8")
    return folder


def test_custom_template_from_dir(tmp_path: Path) -> None:
    template = DeckTemplate.from_dir(_custom_template(tmp_path / "t"))
    template.preflight()
    assert template.name == "tiny"
    assert template.example_words == {"cat"}
    with pytest.raises(TemplateError, match=r"no anki/front\.html"):
        template.anki_file("front.html")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"input_format": "{word} {level}"}, "not in input_vars"),
        ({"name": "Bad Name"}, "invalid"),
        ({"anki": {"note_type": "x", "fields": {"a": "audio:word"}}}, "audio"),
    ],
)
def test_invalid_template_yaml(tmp_path: Path, overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        DeckTemplate.from_dir(_custom_template(tmp_path / "t", **overrides))


def test_missing_files_and_bad_examples(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="missing"):
        DeckTemplate.from_dir(tmp_path)
    folder = _custom_template(tmp_path / "t")
    (folder / "examples.json").write_text('[{"input": {"word": "cat"}, "output": {"t": 1}}]', encoding="utf-8")
    with pytest.raises(TemplateError, match="doesn't match the schema"):
        DeckTemplate.from_dir(folder).preflight()
