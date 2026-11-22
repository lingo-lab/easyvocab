"""Words → an .apkg file you import with File → Import (Anki doesn't need to run).

uv run --extra all examples/apkg_offline.py words.txt german.apkg
"""

import logging
import sys

from easyvocab import (
    GTTS,
    AnkiPackageExporter,
    DeckTemplate,
    LLMCardGenerator,
    OpenAICompatibleLLM,
    Pipeline,
    load_inputs,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

words_path, apkg_path = sys.argv[1], sys.argv[2]
template = DeckTemplate.builtin("de-en-a1b1")
generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
pipeline = Pipeline(generator, AnkiPackageExporter(apkg_path, "German::A1-B1"), tts=GTTS(), workdir=".easyvocab")

result = pipeline.run(load_inputs(words_path))
print(f"{result.export.notes} notes → {apkg_path} (${result.batch.cost_usd:.4f}, {result.missing_audio} clips missing)")
