"""Words → German deck straight in Anki (needs Anki + AnkiConnect running, FIREWORKS_API_KEY set).

uv run --extra all examples/minimal.py words.txt
"""

import logging
import sys

from easyvocab import (
    GTTS,
    AnkiConnectExporter,
    DeckTemplate,
    LLMCardGenerator,
    OpenAICompatibleLLM,
    Pipeline,
    load_inputs,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

template = DeckTemplate.builtin("de-en-a1b1")
generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
pipeline = Pipeline(generator, AnkiConnectExporter("German::A1-B1"), tts=GTTS())

result = pipeline.run(load_inputs(sys.argv[1]))
print(f"{len(result.cards)} cards for ${result.batch.cost_usd:.4f}, failed: {list(result.failures)}")
