"""CI check: the core works without optional extras, and extras fail with an install hint."""

import importlib.util
import sys

from easyvocab import GTTS, AnkiPackageExporter, DeckTemplate, LLMCardGenerator, WordInput
from easyvocab.errors import MissingExtraError
from easyvocab.testing import FakeLLM


def main() -> None:
    """Exit non-zero if the minimal install is broken."""
    for module in ("gtts", "genanki", "tenacity"):
        if importlib.util.find_spec(module):
            sys.exit(f"{module} is installed; this check needs an install without extras")

    template = DeckTemplate.builtin("de-en-a1b1")
    template.preflight()
    output = template.examples[0].output
    card = LLMCardGenerator(FakeLLM([output]), template).generate(WordInput(word=output["word"]))
    if card.fields != output:
        sys.exit("generated card doesn't match the scripted reply")

    for factory, extra in ((GTTS, "tts"), (lambda: AnkiPackageExporter("x.apkg", "x"), "anki")):
        try:
            factory()
        except MissingExtraError as exc:
            if f"easyvocab[{extra}]" not in str(exc):
                sys.exit(f"install hint missing: {exc}")
        else:
            sys.exit(f"expected MissingExtraError for the {extra!r} extra")
    sys.stdout.write("minimal install OK\n")


if __name__ == "__main__":
    main()
