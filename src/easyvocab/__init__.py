"""easyvocab: build Anki vocabulary decks with LLMs.

Example:
    ```python
    from easyvocab import (
        DeckTemplate,
        GTTS,
        AnkiConnectExporter,
        LLMCardGenerator,
        OpenAICompatibleLLM,
        Pipeline,
        load_inputs,
    )

    template = DeckTemplate.builtin("de-en-a1b1")
    generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
    Pipeline(generator, AnkiConnectExporter("German::A1-B1"), tts=GTTS()).run(load_inputs("words.txt"))
    ```
"""

import logging

from easyvocab.batch import BatchGenerator, BatchResult, CardCache
from easyvocab.errors import EasyVocabError
from easyvocab.exporters import AnkiConnectExporter, AnkiPackageExporter, DeckExporter, ExportResult
from easyvocab.generators import CardGenerator, LLMCardGenerator
from easyvocab.inputs import load_inputs
from easyvocab.llm import LLM, GenerationParams, OpenAICompatibleLLM
from easyvocab.models import Card, Completion, Message, Pricing, Usage, WordInput
from easyvocab.pipeline import Pipeline, PipelineResult
from easyvocab.templates import DeckTemplate
from easyvocab.tts import GTTS, TTS

__version__ = "0.1.0"  # x-release-please-version

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "GTTS",
    "LLM",
    "TTS",
    "AnkiConnectExporter",
    "AnkiPackageExporter",
    "BatchGenerator",
    "BatchResult",
    "Card",
    "CardCache",
    "CardGenerator",
    "Completion",
    "DeckExporter",
    "DeckTemplate",
    "EasyVocabError",
    "ExportResult",
    "GenerationParams",
    "LLMCardGenerator",
    "Message",
    "OpenAICompatibleLLM",
    "Pipeline",
    "PipelineResult",
    "Pricing",
    "Usage",
    "WordInput",
    "__version__",
    "load_inputs",
]
