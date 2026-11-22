# easyvocab

[![PyPI](https://img.shields.io/pypi/v/easyvocab)](https://pypi.org/project/easyvocab/)
[![CI](https://img.shields.io/github/actions/workflow/status/lingo-lab/easyvocab/main.yml?branch=main&label=CI)](https://github.com/lingo-lab/easyvocab/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/lingo-lab/easyvocab/branch/main/graph/badge.svg)](https://codecov.io/gh/lingo-lab/easyvocab)
[![Docs](https://img.shields.io/badge/docs-lingo--lab.github.io-blue)](https://lingo-lab.github.io/easyvocab/)
[![License](https://img.shields.io/github/license/lingo-lab/easyvocab)](LICENSE)

Build Anki vocabulary decks with LLMs. A word list goes in. A deck comes out, with grammar, definitions, natural example sentences and audio, for about **$0.001 per word**.

```bash
pip install "easyvocab[all]"
```

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
generator = LLMCardGenerator(OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash"), template)
Pipeline(generator, AnkiConnectExporter("German::A1-B1"), tts=GTTS()).run(load_inputs("words.txt"))
```

## How it works

```
words.txt / words.json ──▶ LLMCardGenerator ──▶ AudioStage (GTTS) ──▶ AnkiConnectExporter / AnkiPackageExporter
                           (template + LLM,      (one mp3 per unique     (note type, notes, media;
                            schema-validated)      text, resumable)        re-imports update notes)
```

- **Templates.** A folder holds the prompt, few-shot examples, a JSON Schema, the Anki layout and the audio fields. Built-in: `de-en-a1b1` and `en-ru`. → [docs/templates](docs/templates.md)
- **Any OpenAI-compatible LLM.** Presets for Fireworks, Nebius and OpenAI, or set a `base_url` for vLLM or Ollama. Every card records `usage`, `cost_usd` and `latency_s`.
- **Resumable.** Cards are cached in sqlite and audio on disk. After a crash or a TTS quota hit, re-run the same command and only the missing work is done.
- **Preflight.** A missing API key, Anki being closed, or a quota hit is reported before anything is spent.
- **Extensible.** Every component is a `Protocol`. → [docs/extending](docs/extending.md)

## Development

```bash
make install   # uv sync --all-extras + pre-commit hooks
make check     # lock, ruff, ty, deptry
make test      # unit tests with coverage
make test-live # real Fireworks call (FIREWORKS_API_KEY, < $0.01)
make docs      # serve the docs locally
```

Releases are automated. Write commits as `feat:` / `fix:`, and release-please opens a release PR. Merging it publishes to PyPI.
