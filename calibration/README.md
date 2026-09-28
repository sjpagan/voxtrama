# Calibration scripts

The text a person reads out loud when they install Voxtrama, so the system
can measure its own transcription against a known reference before a single
real conversation exists.

## Why this lives at the repository root

This material belongs to the product, not to a dev tool: the person doing
the calibration reads it, in whatever language they picked. It is not under
`src/`, because the module that will serve it to that person does not exist
yet. It is not under `tools/`, because it is not a
development tool: `tools/eval/fixtures/generate.py` reads it today, but only
as one more consumer, the same way the eventual calibration module will.
Once that module gives this text a home inside the product, it moves there; until
then, the root is the honest place for something that belongs to neither.

## Format

One file per language, `<language>.yaml`:

```yaml
language: it
version: 1.0.0
passages:
  - id: scripted
    kind: scripted
    text: |
      Buongiorno, sto tarando il riconoscimento vocale.
      ...
  - id: unpredictable
    kind: unpredictable
    text: |
      ...
```

Every script has exactly two passages:

- **`scripted`**: natural sentences in the script's language. What the
  person reads first.
- **`unpredictable`**: real words of the language, strung together without
  making sense, so a language model cannot guess the next one from context.
  On `scripted` text a model can look good by predicting what comes next
  instead of actually hearing it; `unpredictable` text closes that loophole.

`language` and the file name must match: `calibration/it.yaml` declares
`language: it`. Loading goes through `tools/eval/fixtures/calibration.py`,
which lists the languages it finds here if you ask for one that is not.

## Adding a language

Copy an existing file, keep the two passage ids and kinds, and write new
text. That is the whole cost: there is no fixed set of categories a passage
must hit, no schema beyond the one above.

That said, a `scripted` passage that is only easy sentences does not exercise
much. Ones that have worked well include, somewhere in the six or so
sentences: a date and a time, a couple of acronyms spelled out letter by
letter, at least one proper name foreign to the script's language, one very
short sentence, one longer sentence with a subordinate clause, and a loanword
in ordinary use. None of this is enforced. It is what to reach for if a new
script feels thin.

For `unpredictable`, aim for a handful of real, pronounceable words in
scrambled order, a short digit sequence, an alphanumeric code read letter by
letter (a plate, a reference number), and two or three proper names foreign
to the language.

**Do not translate a script from another language.** Every language has its
own traps (acronyms are spelled out differently, numbers have different
shapes, the names that trip a model up are different ones), and a literal
translation tests the source language's difficulties, not the target one's.

**Do not use a famous quotation.** A model has seen well-known quotes many
times during training and will complete them even when it mishears the
audio, which measures its memory instead of its transcription.

## Who reads this today

`tools/eval/fixtures/generate.py` builds the `calibration-*` fixtures from
the `scripted` passage: each line becomes one turn read by the case's
declared voice, so the eval pipeline exercises real calibration text instead
of a stand-in. See `tools/eval/fixtures/calibration.py` for the loader and
`tools/eval/fixtures/calibration-script.md` for why the text looks the way
it does.
