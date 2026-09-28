# The evaluation set

`voxtrama calibrate` measures a configured model against real recordings,
so a badly tuned model shows up as a number instead of a plausible-looking
transcript nobody questions. This page describes the material that measure
needs: where it lives, what already sits there, and how to add the
annotation calibration reads. It does not describe the measure itself,
which is added once this material exists.

You do not need to read any design document to use this page. If a
decision behind a rule matters to you, a link at the end of the relevant
paragraph points at it.

## Where it lives

Point `VOXTRAMA_EVAL_DIR` at a folder on your machine. Nothing under it is
ever committed, and nothing under it ships with Voxtrama: real recordings
carry the voices of identifiable people, and a public repository cannot
take a file back once it has been published. `voxtrama calibrate` runs
fine without this variable set at all, because most machines running
Voxtrama, including CI, never have this material and should not fail for
lacking it. It says so, by name, rather than failing.

## The curated corpus, already there

`reference.csv` at the root of `eval_dir`, plus the clips it lists under
`clips/`, is the material `tests/test_eval_set.py` guards against drift
and `voxtrama calibrate` inventories: one row per clip, each with the
columns that file already declares (`clip`, `speakers`, `overlap`,
`language`, `duration_s`, `notes`):

```
<eval_dir>/
  reference.csv
  clips/
    meeting-01.wav
    lesson-03.wav
    ...
```

Nothing here is new: this is the same corpus already used to keep
diarisation from drifting. Calibration reads it rather than a second
copy, so a clip only needs annotating once to serve both.

### Building a clip

`tests/test_eval_set.py` enforces these on every clip whenever `reference.csv`
is present, so get them right from the start rather than from a failing
test:

- the `.wav` under `clips/` must be **16 kHz, mono**;
- `duration_s` must match that file's real duration, within one second;
- `overlap` is `yes`, `no`, or left blank, nothing else;
- `speakers`, once filled in, is a positive whole number.

### A separate, older kind of material

`eval_dir` may also hold loose `<id>.wav` / `<id>.rttm` pairs at its root:
`tests/test_transcription_asr.py`'s own material, read directly from
the environment variable rather than through the corpus above. An
`.rttm` file is a **diarisation reference**: which speaker was talking,
and when, not a transcript of what was said. It predates the curated
corpus, is not listed in `reference.csv`, and `voxtrama calibrate` does
not inventory it: it exists for that one test, not for calibration.

## The annotation file

An annotation adds one file per clip, next to it under `clips/`, named
after the clip's own file name with its extension replaced:
`clips/meeting-01.annotation.yaml` for `clips/meeting-01.wav`. This file
does not exist yet anywhere. Writing it for a real clip comes next; this
page only fixes its shape, so that work has a contract to write to.

```yaml
clip: meeting-01.wav
fields:
  - skill: extract_decisions
    field: decision
    text: "Rimandare il lancio di due settimane"
    interval: { start: 41.2, end: 47.8 }
  - skill: extract_decisions
    field: owner
    text: "Marco"
    interval: { start: 41.2, end: 41.9 }
salient_passages:
  - interval: { start: 12.0, end: 18.4 }
    note: "the decision to change supplier: a summary missing this is wrong"
```

- **`fields`**: one entry per value a skill is expected to produce from
  this clip. `skill` and `field` name which skill and which of its own
  output fields this is (see the skill's own file under `skills/` for the
  fields it declares); `text` is what a correct answer should say, for a
  person comparing by eye; `interval` is where in the transcript it
  belongs (see below for how to write one).
- **`salient_passages`**: the passages a correct summary must cover,
  independently of any one skill's fields. A summary that leaves one of
  these out is wrong even if every field it did produce checks out.

Nothing here is graded by this page: what counts as a match, and the
score that comes out of comparing an annotation to a real run, is a
separate piece of work. This file only fixes what "correct" means so that
later measure has something to compare against.

## How to write an interval

**One way, always: `{ start: <seconds>, end: <seconds> }`, both counted
from the beginning of the clip, and half-open: `end` is the first
instant no longer included.** This is not a new convention: it is exactly
the shape `evidence` already takes on every anchored claim (see
`engine/anchoring.py`), and the interval query the engine itself runs
against a transcript (`engine/anchor_index.py`, `AnchorIndex.covers`).
Two annotations written two different ways would make a measure that
compares them meaningless, so this page declares the one way rather than
letting a second convention appear the first time someone writes an
annotation by hand.

## The set's own revision

An evaluation set changes over time (a clip gets added, an annotation
gets corrected), and a calibration result is only meaningful next to the
state of the set it was measured against. This, too, does not exist yet:
it is a new part of the contract this page adds, not something the
material already carries. Write a single line naming that state to
`REVISION` at the root of `eval_dir`:

```
<eval_dir>/
  REVISION
```

Any short, stable label works: a date, a short description, a commit
hash of wherever the set itself is tracked. `voxtrama calibrate` reads
and reports it; archiving it alongside every calibration outcome is what
makes two results comparable at all.
