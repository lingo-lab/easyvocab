# Templates

A template is a folder that holds everything for one kind of deck. The built-in ones live in [`src/easyvocab/templates/builtin/`](https://github.com/lingo-lab/easyvocab/tree/main/src/easyvocab/templates/builtin). The easiest way to start is to copy one.

```
my-template/
  template.yaml        name, language, input vars/format, audio, Anki fields
  instruction.md       system prompt
  examples.json        few-shot examples: [{"input": {...}, "output": {...}}]
  output_schema.json   JSON Schema every generated card must match
  anki/                front.html, back.html, style.css
```

```python
template = DeckTemplate.from_dir("my-template")
template.preflight()  # every example matches the schema and the input vars
```

## What the model sees

The prompt is built from four parts:

1. `instruction.md` as the system message.
2. Each example as a user turn (`input_format` filled with the example's input).
3. The example's output as an assistant turn, sent as a ```json block.
4. The word as the last user turn.

Everything except the last turn is identical for every word. Providers with prompt caching (Fireworks, OpenAI) therefore bill most input tokens at the cached price: about 95% of tokens are cached for `de-en-a1b1`.

## `template.yaml`

```yaml
name: de-en-a1b1               # lowercase, digits, . _ -
version: "1"                   # bump it to invalidate cached cards
description: ...
language: de                   # language of the words (TTS)

input_vars: [word]             # keys every input must have (word, context, or extra keys)
input_format: "{word} (hint: {spelling})"
                               # derived var: spelling = capitalized | lowercase | multi-word, ...

audio:                         # audio name → path of the text to speak
  word: tts_text
  example1: examples.0.de

anki:
  note_type: German Vocab (easyvocab)
  card_types:                  # default: one card from front.html / back.html
    - {name: English → German, front: front.html, back: back.html}
  css: style.css
  fields:                      # Anki field → value; the first field is the sort field
    word_de: lemma             # a path into the card
    headword: "{article} {lemma}"   # a format string
    word_audio: audio:word     # [sound:...] for an audio entry
    example1_de: examples.0.de
  tags: [german]               # static tags
  tags_from: [pos]             # field values as tags
  flag_tags: {separable: trennbar}  # tag added when a boolean field is true
```

Value rendering: `true` becomes `yes` and `false` becomes an empty string (so `{{#field}}...{{/field}}` works in Anki), lists become comma-separated, and HTML is escaped.

## Cache

A cached card is reused only when `version`, `input_format`, the instruction, the examples and the schema are all unchanged. Changing `anki/` or the `anki:` section never regenerates cards: the next export simply uses the new layout.

## Keep few-shot words out of evaluations

`template.example_words` lists the words used as examples, so you can filter them out of an eval set.
