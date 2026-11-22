# Extending

Every extension point is a `typing.Protocol`, so you don't inherit from anything: write a class with the right methods and pass it in. Errors should be `easyvocab.errors.EasyVocabError` subclasses, which keeps the messages user-facing.

| protocol | methods | built-in |
|---|---|---|
| `LLM` | `model`, `fingerprint`, `complete(messages) -> Completion`, `preflight()` | `OpenAICompatibleLLM` |
| `CardGenerator` | `template`, `fingerprint`, `generate(word) -> Card`, `preflight()` | `LLMCardGenerator` |
| `TTS` | `fingerprint`, `synthesize(text, lang) -> bytes`, `preflight(lang)` | `GTTS` |
| `DeckExporter` | `export(cards, template, media_dir) -> ExportResult`, `preflight(template)` | `AnkiPackageExporter`, `AnkiConnectExporter` |

## Any OpenAI-compatible server (vLLM, Ollama, LM Studio, ...)

```python
from easyvocab import GenerationParams, OpenAICompatibleLLM, Pricing

llm = OpenAICompatibleLLM(
    "qwen3-8b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    params=GenerationParams(temperature=0.2, extra_body={"top_k": 20}),
    pricing=Pricing(input_per_million=0, output_per_million=0),
)
```

## A new exporter: CSV

```python
import csv
from pathlib import Path

from easyvocab import Card, DeckTemplate, ExportResult


class CsvExporter:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def preflight(self, template: DeckTemplate) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, cards: list[Card], template: DeckTemplate, media_dir: Path) -> ExportResult:
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(cards[0].fields))
            writer.writeheader()
            writer.writerows(card.fields for card in cards)
        return ExportResult(notes=len(cards), path=self.path, destination=str(self.path))
```

## Testing your code

`easyvocab.testing` provides `FakeLLM`, `FakeTTS` and `FakeExporter`:

```python
from easyvocab.testing import FakeExporter, FakeLLM, FakeTTS

llm = FakeLLM([card_fields])  # scripted replies, in order
llm = FakeLLM(respond=lambda messages: {...})  # or computed from the prompt
Pipeline(LLMCardGenerator(llm, template), FakeExporter(), tts=FakeTTS(limit=10)).run(words)
```
