"""Research use: generate cards for several models without TTS/Anki, compare cost and latency.

uv run examples/research_batch.py words.txt
"""

import logging
import sys

from easyvocab import BatchGenerator, CardCache, DeckTemplate, LLMCardGenerator, OpenAICompatibleLLM, load_inputs

logging.basicConfig(level=logging.INFO, format="%(message)s")

template = DeckTemplate.builtin("de-en-a1b1")
words = [word for word in load_inputs(sys.argv[1]) if word.word not in template.example_words]

with CardCache("runs/cache.sqlite") as cache:
    for model in ("deepseek-v4p1-flash", "glm-5p3", "kimi-k3"):
        generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks(model), template)
        result = BatchGenerator(generator, cache=cache).run(words)
        latency = sum(card.latency_s for card in result.cards) / max(len(result.cards), 1)
        print(
            f"{model}: {len(result.cards)} cards, ${result.cost_usd:.4f}, {latency:.1f}s/word, failed {list(result.failures)}"
        )
