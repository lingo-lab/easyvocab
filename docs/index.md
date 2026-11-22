# easyvocab

Build Anki vocabulary decks with LLMs: a word list goes in, and a deck with grammar, definitions, natural example sentences and audio comes out, for about **$0.001 per word**.

## Install

```bash
pip install "easyvocab[all]"      # or: uv add "easyvocab[all]"
```

| extra | adds | needed for |
|---|---|---|
| (none) | pydantic, httpx, openai, jsonschema, pyyaml | generating cards (research, custom exporters) |
| `tts` | gTTS, tenacity | `GTTS` audio |
| `anki` | genanki | `AnkiPackageExporter`, `AnkiConnectExporter` |
| `all` | everything above | |

## Quickstart

```python
from easyvocab import (
    GTTS,
    AnkiConnectExporter,
    DeckTemplate,
    LLMCardGenerator,
    OpenAICompatibleLLM,
    Pipeline,
    load_inputs,
)

template = DeckTemplate.builtin("de-en-a1b1")
llm = OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash")  # reads FIREWORKS_API_KEY (env or .env)
generator = LLMCardGenerator(llm, template)

pipeline = Pipeline(generator, AnkiConnectExporter("German::A1-B1"), tts=GTTS())
result = pipeline.run(load_inputs("words.txt"))  # .txt (one word per line), .json or .jsonl
print(len(result.cards), result.batch.cost_usd, result.failures)
```

What `run` does:

1. **Preflight.** Checks the API key, the model id, the template, Anki and the TTS quota, and reports every problem at once before anything is spent.
2. **Generate.** Calls the LLM in parallel and validates each card against the template's JSON Schema. If a reply is invalid, the model sees its errors and tries again.
3. **Audio.** Voices every audio field once. Identical texts share one file.
4. **Export.** Builds the note type, the notes and the media. Re-importing updates the existing notes instead of duplicating them.

Every stage is resumable. Cards are cached in `.easyvocab/cache.sqlite` and audio is kept in `.easyvocab/media/`. If a run crashes or the Google TTS quota runs out, run the same command again and only the missing work is done.

No Anki running? Use `AnkiPackageExporter("german.apkg", "German::A1-B1")` and import the file with File → Import.

## Research use

Use `BatchGenerator` when you only need cards, without TTS or Anki. Every card carries `usage`, `cost_usd`, `latency_s`, `attempts` and `model`. The cache key is `hash(template, model + params, word, context)`.

```python
from easyvocab import BatchGenerator, CardCache

with CardCache("runs/cache.sqlite") as cache:
    result = BatchGenerator(generator, cache=cache, workers=8).run(words)
```

## Built-in templates

| name | language | cards |
|---|---|---|
| `de-en-a1b1` | German → English, A1–B1 | 1 (English → German), with word + 2 example audios |
| `en-ru` | English → Russian | 2 (ru → en, en → ru), with word audio |

To write your own template, see [Templates](templates.md). To plug in another LLM, TTS or exporter, see [Extending](extending.md).
