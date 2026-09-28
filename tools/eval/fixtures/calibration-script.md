# Calibration script

The person installing Voxtrama reads a short text out loud once; the system
transcribes it and scores itself against the known reference. Nobody is
asked to judge the transcript: the reference text **is** the ground truth.

The text itself is not here: it lives in `calibration/` at the repository
root, one file per language (`calibration/it.yaml`, `calibration/en.yaml`,
...). See `calibration/README.md` for the format and for how to add a
language. This document only explains the criteria behind it.

The same text is what the synthetic voices read in the `calibration-*`
fixtures (`cases.yaml`), via `calibration_script` and `voice` on the case, so
a run on a real person and a run on a synthetic voice are directly
comparable.

## Two passages, and why

Each script has two passages:

- **`scripted`**: natural sentences, the reference text. Built to include a
  date and a time, a couple of acronyms spelled out letter by letter,
  proper names foreign to the script's language, one very short sentence, a
  longer sentence with a subordinate clause, and a loanword in ordinary use.
  These are the ordinary places a transcription goes wrong: numbers before
  normalisation, an acronym spelled by some models and run together by
  others, a name outside the language model's comfort zone, a very short
  utterance that an aggressive VAD trims entirely, punctuation and
  segmentation across a longer sentence, and a word borrowed from another
  language that might make the model switch language mid-sentence.
- **`unpredictable`**: real words strung together without making sense,
  plus a digit sequence and a code read letter by letter, and foreign proper
  names. It exists because a model can look good on `scripted` text by
  predicting the next word from context instead of actually hearing it;
  `unpredictable` text closes that loophole.

## What scoring this requires

**Number normalisation before comparison.** The reader says «nove e
quarantacinque», the model may write `9:45`, and a naive word-by-word
comparison would call that an error. Without normalisation the score
measures formatting, not recognition.
