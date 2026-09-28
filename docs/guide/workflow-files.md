# Writing a workflow

A workflow is a YAML file that tells Voxtrama what to do with a recording:
which skills to run, in what order, and what to do when one of them fails.
This page tells you how to write one, what each field means, and what
Voxtrama says when a field is wrong.

You do not need to read any design document to use this page. If a
decision behind a rule matters to you, a link at the end of the relevant
paragraph points at it. The paragraph itself stands on its own.

## Vocabulary

A **skill** is a single unit of work with a fixed contract: given some
input, it produces output of a known shape. `transcribe` turns audio into
text. `extract_decisions` turns a transcript into a list of decisions,
each tied to a quote. A skill is not something you write here: it already
exists, built into Voxtrama or declared in a file under `skills/`. You
name one; you do not define one. (Writing a new skill is a different task,
for a different audience, and is out of scope for this page.)

A **step** is one skill, placed into a workflow: which skill to run, which
earlier steps it needs to have finished first, and what to do if it fails.
A workflow with three steps runs the same skill logic three times over,
each time wired to the others differently.

A **workflow** is a named, versioned list of steps. It is the thing you
give to `voxtrama run`. Steps form a graph, not a straight line: a step
can depend on more than one earlier step, and two steps with no
dependency between them can run in either order, or in parallel.

## The workflow's own fields

These fields sit above the list of steps:

- `name`: the workflow's identifier. It is also, by convention, the file
  name without `.yaml`: `transcribe-only.yaml` holds `name: transcribe-only`.
  `voxtrama run <name> ...` looks the file up by this file name, not by
  reading the field, so the two staying in step is on you, not something
  Voxtrama checks.
- `version`: a version you choose for the workflow itself, for example
  `1.0.0`. It has no required format today.
- `schema_version`: which shape of workflow file this is. This version of
  Voxtrama reads `v1`, matching `schemas/workflow-v1.json` in the
  repository, and refuses any other value. Until 1.0 there is no
  compatibility promise: an update may change the shape, and its release
  notes say how to adapt your files.
- `description`: a sentence or two, for a person reading the file, not
  for the engine.
- `privacy`: optional. `local_only` keeps every step's content on this
  machine, even for a skill that declares `any`: a run on a remote model
  server is refused before it starts. It only narrows; leave it out (or
  write `any`) and each skill's own declaration holds.
- `steps`: the list documented below.

## The skills available today

A step's `skill` field must name one of these, at `skill_version: 1.0.0`:

| Skill | What it does |
|---|---|
| `transcribe` | audio to text |
| `diarize` | labels each transcript segment with the voice that spoke it |
| `summarize` | a transcript to a summary |
| `extract_decisions` | a transcript to decisions, each with an owner, a deadline and a supporting quote |
| `extract_concepts` | a transcript to key concepts and definitions |
| `extract_themes` | a transcript to themes, each with a supporting quote |

Naming anything else fails to load: see "Unknown skill" below.

## A step's fields

Each entry in `steps` is one of these:

- **`id`**: a name for this step, unique within the workflow. Other steps
  refer to it by this string, in `depends_on`, `condition` and
  `on_error.fallback_step`.
- **`skill`**: the name of the skill this step runs, from the table
  above.
- **`skill_version`**: the version of that skill, `1.0.0` for everything
  listed above. Both `skill` and `skill_version` must resolve together: a
  real skill with a version that does not exist fails the same way an
  unknown skill name does.
- **`depends_on`**: a list of step ids that must finish, successfully,
  before this step starts. Leave it empty (or omit it) for a step that can
  start as soon as the run does. A step id that is not in this workflow
  fails to load.
- **`condition`**: whether this step runs at all, evaluated once its
  dependencies have finished. Omit it to always run the step. When
  present, it is exactly one comparison: `<path> <operator> <literal>`,
  for example `steps.transcribe.state == "succeeded"` or
  `recording.duration_seconds > 3600`. Nothing richer than that is
  accepted: no `and`, no `or`, no function calls. This is deliberate:
  a condition is data, not code, so a workflow file from someone you do
  not know cannot do more than branch.
  The path is one of a fixed set: `recording.duration_seconds`,
  `recording.media_type`, `transcript.language`, `transcript.speaker_estimate`,
  or `steps.<id>.<key>` reading an earlier step's own output field.
  `steps.<id>.state` is a special case: it reads whether that step
  `succeeded`, `failed` or `skipped`, not something the step produced, and
  only `==`, `!=`, `in` and `not in` make sense against it. A step whose
  condition reads `steps.<id>.state` must also depend on `<id>`, directly
  or through another step, so that step is guaranteed to have already
  run.
- **`on_error`**: what happens when this step fails. It has two parts:
  - `retry.max_attempts`: how many times to retry before giving up.
    Defaults to `0`: fail on the first attempt.
  - `fallback_step`: the id of a step to run instead, once retries are
    exhausted. Left unset, the step's own failure fails the run. A
    `fallback_step` naming a step id that is not in this workflow fails to
    load.
- **`allows`**: what a run is permitted to swap in for this step, chosen
  when the run is started rather than fixed in the file. Leave it out and
  nothing can be swapped: an empty `allows` is not "anything goes", it is
  "nothing offered here". Two lists:
  - `skills`: alternative `skill` / `skill_version` pairs a run may pick
    instead of this step's own. Each one must itself be a real skill and
    version, checked at load time, before the run reaches it. An
    alternative that turns out not to exist should fail before the slow
    steps ahead of it run, not after.
  - `models`: model names a run may pick between, for whichever skill
    ends up running this step.
- **`privacy`**: optional, the same as the workflow's but for this step
  alone: `local_only` keeps this one step on the machine (for example the
  recap, while the rest may use a remote server). It cannot let out a
  step its skill or its workflow keeps local.

## Fields you will read, not write

These fields live on the **skill**, not
on the step. You read them to understand what a skill promises, you do
not set them in a workflow file:

- **`evidence_required`** answers: does every claim this skill produces
  have to anchor back to an exact passage of the transcript? When it is
  `true`, a claim the engine cannot re-anchor is a failed step, not a
  claim shipped anyway. `extract_decisions` is stricter about the shape of
  its output (a `quote` field on every decision) than it is about this
  flag: see the skill's own file for which value it declares.
- **`minimum_confidence`** is declared by every skill and is a number
  between 0 and 1. A skill file with a value outside that range is
  rejected. Nothing in the engine reads it yet: what a confidence score
  means, and what a run should do with output below the threshold, is an
  open decision, so this field records an intent and changes no behaviour
  today. Do not write a workflow that counts on it.
- **`retention_policy`** says how long what the skill produces may stay:
  `follows_recording` (no limit of its own) or a number of days, `30d`.
  A workflow lives under the shortest its skills declare, and so does
  every job it runs: an installation's limit or a job's own choice can
  shorten that, never lengthen it. Any other value is rejected.

## Errors the loader catches

Voxtrama validates a workflow before a run ever starts: importing audio
and enqueuing work only happen once the file above has already passed.
Every message below is quoted from a real, broken file, loaded with the
real loader; each names the field's path so you know exactly where to
look.

A field missing or the wrong type:

```
Invalid workflow: <path to your file>: steps.0.skill_version: Field required
```

A `schema_version` this version does not read:

```
Invalid workflow: <path to your file>: schema_version: Input should be 'v1'
```

A field the schema does not know (a typo in a field name, most often):

```
Invalid workflow: <path to your file>: steps.0.retries: Extra inputs are not permitted
```

A step names a skill, or a skill version, that does not exist:

```
Invalid workflow: steps[1].skill: unknown skill 'not_a_real_skill' version '1.0.0'
```

A step's `depends_on` names a step id that is not in this workflow:

```
Invalid workflow: steps[1].depends_on: unknown step 'does_not_exist'
```

A step's `on_error.fallback_step` names a step id that is not in this
workflow:

```
Invalid workflow: steps[0].on_error.fallback_step: unknown step 'does_not_exist'
```

Two steps depend on each other, directly or through a longer chain:

```
Invalid workflow: steps: dependency cycle: a -> b -> a
```

A `condition` that does not parse as `<path> <operator> <literal>`:

```
Invalid workflow: steps[1].condition: condition names a path outside the allowed list: 'this' in 'this is not a condition'
```

A `condition` naming a step id that is not in this workflow:

```
Invalid workflow: steps[1].condition: unknown step 'nope'
```

A `condition` on `steps.<id>.state` comparing against something that is
not a state a step can reach:

```
Invalid workflow: steps[1].condition: 'done' is not a state a step can reach; use one of ['failed', 'skipped', 'succeeded']
```

An `allows.skills` entry naming a skill, or version, that does not exist:

```
Invalid workflow: steps[1].allows.skills[0]: unknown skill 'not_a_real_skill' version '1.0.0'
```

A workflow name that resolves to no file at all:

```
Unknown workflow: no workflow named '<name>' in: <your data directory>/workflows, <the package's own workflows/>
```

## A workflow, commented

This is `workflows/meeting-decisions.yaml` from the repository,
with a comment on the purpose of each line rather than its syntax:

```yaml
name: meeting-decisions       # matches the file name, meeting-decisions.yaml
title: Meeting decisions       # read by a person, on every page that lists workflows
version: 2.0.0                 # this workflow's own version, chosen by its author
schema_version: v1             # the shape this file follows, see schemas/workflow-v1.json
description: >
  Turns a meeting recording into decisions, owners and deadlines, each
  traceable back to the audio.
steps:
  - id: transcribe             # named so a later step can depend on it
    skill: transcribe
    skill_version: 1.0.0
    # no depends_on: this is where the run starts

  - id: diarize
    skill: diarize
    skill_version: 1.0.0
    depends_on: [transcribe]   # needs transcribe's output; runs after it

  - id: extract_decisions
    skill: extract_decisions
    skill_version: 1.0.0
    depends_on: [diarize]      # needs speakers told apart, not just text
    allows:
      skills:
        # a run may pick extract_themes instead: same shape of promise
        # (a structured, anchored list), a different question asked of
        # the same transcript
        - skill: extract_themes
          skill_version: 1.0.0
      models:
        # a run may pick either model for whichever skill it ends up
        # running here, without needing a second workflow file
        - qwen2.5:0.5b
        - qwen3:30b
```

Nothing here sets `condition` or `on_error`: this workflow always runs all
three steps, in order, and a failed step fails the run. See "A
step's fields" above for what those look like when a workflow does use
them.

## Running it

```
voxtrama run <workflow-name> <path-to-audio-file>
```

This validates the workflow first: you will see one of the messages
above, and nothing gets imported or enqueued, if it does not pass. Once it
does, Voxtrama imports the audio, enqueues the run, and prints progress as
the worker executes it. `--detach` prints the run id and exits instead of
following it.

**`--reuse-from <run-id>`** reuses that earlier run's own step
outputs wherever their `reuse_key` still matches this run's, the same
recording, the same skill, the same choices, up to and including the last
step that changed. Everything after that point is recomputed, so
rerunning a workflow that only edits its last step (a different
`summarize` skill_version, say) does not repeat transcription or
diarization. An unknown run id fails immediately, before anything is
imported. `steps[].reused_from_run_id` in the manifest says which steps
were reused and from where.

**When a run fails partway through**, the command's own exit code is `1`.
Look inside the run's own folder,
`<data directory>/runs/<run-id>/`:

- `manifest.json` has a `failure` object once the run has failed:
  `code`, `message` and which `step` it happened in;
- `run.log` has every log line the worker produced with this run's id,
  in order, including whatever the failing step itself reported.

## Where to look next

`schemas/workflow-v1.json` in the repository is the exact,
generated shape a workflow file must match: every field, every type,
nothing this page describes in prose that the schema does not also state
formally. Point an editor or a validator at it for the field you are
unsure about while writing.
