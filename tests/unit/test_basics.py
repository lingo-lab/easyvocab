import json
from pathlib import Path

import pytest

from easyvocab._jsonpath import render, resolve, to_text
from easyvocab.errors import CardValidationError, ConfigurationError
from easyvocab.inputs import load_inputs
from easyvocab.llm.json_output import extract_json
from easyvocab.models import Pricing, Usage, WordInput

DATA = {"lemma": "Haus", "article": "das", "examples": [{"de": "Hallo"}], "separable": True, "tags": ["a", "b"]}


@pytest.mark.parametrize(
    ("path", "expected"),
    [("lemma", "Haus"), ("examples.0.de", "Hallo"), ("examples.1.de", None), ("missing.path", None)],
)
def test_resolve(path: str, expected: object) -> None:
    assert resolve(path, DATA) == expected


def test_render_paths_and_format_strings() -> None:
    assert render("{article} {lemma}", DATA) == "das Haus"
    assert render("{article} {lemma}", {"lemma": "gehen", "article": ""}) == "gehen"
    assert render("examples.0.de", DATA) == "Hallo"
    assert render("separable", DATA) == "yes"


def test_to_text() -> None:
    assert [to_text(value) for value in (None, False, True, ["a", "", "b"], 3)] == ["", "", "yes", "a, b", "3"]


def test_word_input_normalizes_whitespace_and_keeps_extras() -> None:
    word = WordInput.model_validate({"word": "  Rad   fahren ", "context": "a\nb", "level": "B1"})
    assert (word.word, word.context) == ("Rad fahren", "a b")
    assert word.variables()["level"] == "B1"


def test_usage_add_and_pricing() -> None:
    usage = Usage(1_000_000, 1_000_000, 500_000) + Usage(0, 0, 0)
    pricing = Pricing(input_per_million=1.0, output_per_million=2.0, cached_input_per_million=0.1)
    assert pricing.cost(usage) == pytest.approx(0.5 + 0.05 + 2.0)
    assert Pricing(1.0, 2.0).cost(usage) == pytest.approx(3.0)


@pytest.mark.parametrize(
    "text",
    ['```json\n{"a": 1}\n```', 'Sure! {"a": 1} hope it helps', '```\n{"a": 1}\n```'],
)
def test_extract_json(text: str) -> None:
    assert extract_json(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "no json here", "```json\n{broken\n```", "[1, 2]"])
def test_extract_json_errors(text: str) -> None:
    with pytest.raises(CardValidationError):
        extract_json(text)


def test_load_inputs_formats(tmp_path: Path) -> None:
    (tmp_path / "w.txt").write_text("Haus\n\n# comment\nje ... desto ...\nHaus\n", encoding="utf-8")
    (tmp_path / "w.json").write_text(json.dumps(["Haus", {"word": "Baum", "context": "im Wald"}]), encoding="utf-8")
    (tmp_path / "w.jsonl").write_text('{"word": "Tisch"}\n\n{"word": "Stuhl"}\n', encoding="utf-8")
    assert [w.word for w in load_inputs(tmp_path / "w.txt")] == ["Haus", "je ... desto"]
    assert [(w.word, w.context) for w in load_inputs(tmp_path / "w.json")] == [("Haus", ""), ("Baum", "im Wald")]
    assert [w.word for w in load_inputs(tmp_path / "w.jsonl")] == ["Tisch", "Stuhl"]


def test_load_inputs_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load_inputs(tmp_path / "missing.json")
    (tmp_path / "w.csv").write_text("x", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Unsupported"):
        load_inputs(tmp_path / "w.csv")
    (tmp_path / "bad.json").write_text('[{"context": "no word"}]', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="item #0"):
        load_inputs(tmp_path / "bad.json")
