# Workflow files

A workflow is a YAML file that tells Voxtrama which skills to run on a recording, in what order, and what to do when one of them fails. A new workflow needs no code. The file goes in the `workflows/` folder of the data folder, and Voxtrama checks it before any job starts.

The Workflows page can also build a custom workflow from skills that already exist, without writing YAML. This page is for writing or reading the file itself.

## Vocabulary

A skill is one unit of work with a fixed contract. `transcribe` turns audio into text. `extract_decisions` turns a transcript into a list of decisions, each tied to a quote. A workflow file names skills and does not define them.

A step is one skill placed in a workflow, with the earlier steps it needs and what to do if it fails.

A workflow is a named, versioned list of steps. Steps form a graph: a step can depend on several earlier steps.

## Skills available

A step's `skill` field must name one of these skills, with `skill_version: 1.0.0`.

| Skill | Kind | What it does | Runs where |
|---|---|---|---|
| `transcribe` | built in | audio to text, with Whisper | always on this machine |
| `diarize` | built in | labels each transcript segment with the voice that spoke it | always on this machine |
| `summarize` | file in `skills/` | a transcript to a recap | on the model server |
| `extract_decisions` | file in `skills/` | a transcript to decisions, each with an owner, a deadline and a supporting quote | on the model server |
| `extract_concepts` | file in `skills/` | a transcript to key concepts and definitions | on the model server |
| `extract_themes` | file in `skills/` | a transcript to themes, each with a supporting quote | on the model server |

Any other skill name fails to load. A skill file that fails to load makes the skill unknown, and the error says why (see Errors the loader catches).

## Workflow fields

These fields sit at the top of the file, before the list of steps.

| Field | Required | What it holds |
|---|---|---|
| `name` | yes | the identifier, lowercase and hyphenated, equal to the file name without `.yaml` |
| `title` | no | the name a person reads on every page that lists workflows; without it, the pages show a formatted `name` |
| `version` | yes | a version you choose for the workflow, for example `1.0.0`; no format is enforced |
| `schema_version` | yes | the shape of the file; this version of Voxtrama reads `v1` and refuses any other value |
| `description` | yes | one line for the person choosing a workflow |
| `privacy` | no | `any` (the default) or `local_only` |
| `steps` | yes | the list of steps |

`voxtrama run <name>` and the job form look the file up by its file name and not by the `name` field, so keeping the two equal is up to you. The name must match `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`: letters, digits, `-` and `_`, starting with a letter or a digit, up to 128 characters. A name that does not match is answered with `no workflow called '<name>': not a valid name`.

`schema_version` is `v1` and only `v1`. Before version 1.0 of Voxtrama there is no compatibility promise: an update may change the shape, and its release notes say how to adapt your files. The exact shape is generated into `schemas/workflow-v1.json` in the repository; point an editor or a validator at that file.

`privacy: local_only` keeps every step's content on this machine, even for a skill that declares `any`. A job that would send such a step to a remote model server is refused before it starts. The field only narrows: leave it out, or write `any`, and each skill's own declaration holds.

## Step fields

| Field | Required | What it holds |
|---|---|---|
| `id` | yes | a name for the step, unique in the workflow; other fields refer to it |
| `skill` | yes | the skill the step runs |
| `skill_version` | yes | the skill's version, `1.0.0` for every skill listed; the pair must exist |
| `depends_on` | no | the ids of the steps that must finish before this one starts; empty or missing means the step can start with the job |
| `condition` | no | whether the step runs at all |
| `on_error` | no | what happens when the step fails |
| `allows` | no | what a job may swap in for this step |
| `privacy` | no | `local_only` keeps this one step on this machine; it cannot let out a step its skill or workflow keeps local |
| `instructions` | no | the step's own instructions in place of its skill's prompt |

### Order of execution

Voxtrama runs one step at a time. A step runs after every step it depends on, and steps that are ready together run in the order they appear in the file. The same workflow therefore always runs in the same sequence.

A step whose dependency was skipped is skipped too. A step that fails, after its retries and its `fallback_step` if it has one, stops the job, and the steps after it do not run. A step that another step names as its `fallback_step` runs only as that step's recovery.

### condition

A condition is exactly one comparison: `<path> <operator> <literal>`. Nothing richer is accepted: no `and`, no `or`, no function calls. A condition is data, so a workflow file from someone you do not know can branch and do nothing more.

```yaml
condition: recording.duration_seconds > 3600
```

| Part | Allowed values |
|---|---|
| path | `recording.duration_seconds`, `recording.media_type`, `transcript.language`, `transcript.speaker_estimate`, or `steps.<id>.<key>` for a field of an earlier step's output |
| operator | `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not in` |
| literal | JSON: strings in double quotes, numbers and lists as in JSON |

Because the literal is JSON, a string needs double quotes, and the whole condition needs quotes in YAML: `condition: 'transcript.language == "it"'`.

`steps.<id>.state` is a special path. It reads whether that step `succeeded`, `failed` or `skipped`, and not something the step produced.

- Only `==`, `!=`, `in` and `not in` are accepted on it. Another operator is refused when the file loads.
- The literal must be one of `"succeeded"`, `"failed"` or `"skipped"`.
- The step that holds the condition must depend on `<id>`, directly or through another step, so that `<id>` has already run.
- A skill that declares its own `state` output property cannot be read this way.

A list literal with `in` on a step's state is not supported. Use a single string with `==` or `!=`, for example `steps.diarize.state == "failed"`.

### on_error

| Field | Default | What it does |
|---|---|---|
| `retry.max_attempts` | `0` | how many times the step is tried again before giving up; `0` fails on the first attempt |
| `fallback_step` | none | the id of a step to run instead, once the retries are used up; without it, the step's failure fails the job |

Retries apply only to `transcribe` and `diarize`. A step that runs a generative skill is never retried inside the job, whatever `max_attempts` says, because a failed call may already have produced output. A `fallback_step` that names a step not in the workflow fails to load.

### allows

`allows` lists what a job may choose for the step when it is started. An empty or missing `allows` means nothing can be swapped; it does not mean anything goes.

| Field | What it holds |
|---|---|
| `skills` | alternative `skill` and `skill_version` pairs a job may pick instead of the step's own; each pair must exist, and is checked when the file loads |
| `models` | model names a job may pick between, for whichever skill runs in the step |

### instructions

`instructions` replaces the prompt of a generative step in this workflow. The skill itself is not changed, and the step's answer must still fit the skill's output fields. The text is a template with three placeholders: `{transcript}`, `{language}` and `{detail}`. `{transcript}` must appear, and a literal brace is written twice, as `{{` or `}}`.

The Workflows page checks the text when you save it, and refuses an unknown placeholder or a missing `{transcript}`. Start from the skill's own instructions, which the Workflows page shows. The check runs when you save on that page. A file edited by hand is not checked when it is loaded, so an unknown placeholder in it makes the step fail when the job runs.

## Fields of a skill

These fields belong to the skill, not to the step. You read them to learn what a skill promises, and you do not set them in a workflow file.

| Field | Meaning |
|---|---|
| `evidence_required` | `false` in all four skill files shipped. Whatever the flag says, the engine anchors every quote of a generative step against the transcript, and a quote it cannot find is marked **Needs review** |
| `minimum_confidence` | a number from 0 to 1, declared by every skill; nothing in the engine reads it yet, so a workflow cannot count on it |
| `retention_policy` | `follows_recording`, or a number of days such as `30d`; a workflow lives under the shortest limit its skills declare, and a job under the shortest of the installation, the workflow and the job |
| `privacy` | `local_only` for `transcribe` and `diarize`, `any` for the four generative skills |

## A workflow, commented

This is `workflows/meeting-decisions.yaml`, the workflow shipped for meetings, with a comment on the purpose of each part.

```yaml
name: meeting-decisions        # equal to the file name, meeting-decisions.yaml
title: Meeting decisions       # what a person reads on the pages that list workflows
version: 2.0.0                 # the workflow's own version, chosen by its author
schema_version: v1             # the shape of the file, see schemas/workflow-v1.json
description: Turn a meeting into decisions, owners and next steps.
steps:
  - id: transcribe             # named so that later steps can depend on it
    skill: transcribe
    skill_version: 1.0.0
    # no depends_on: the job starts here

  - id: diarize
    skill: diarize
    skill_version: 1.0.0
    depends_on: [transcribe]   # needs the transcript; runs after it

  - id: summarize
    skill: summarize
    skill_version: 1.0.0
    depends_on: [diarize]      # the recap says who spoke, so it waits for the speakers

  - id: extract_decisions
    skill: extract_decisions
    skill_version: 1.0.0
    depends_on: [diarize]      # runs after summarize, because it comes later in the file
    allows:
      skills:
        # a job may pick extract_themes instead: another question asked of
        # the same transcript, with a structured, anchored answer
        - skill: extract_themes
          skill_version: 1.0.0
      models:
        # a job may pick either model for whichever skill runs here,
        # without a second workflow file
        - qwen2.5:0.5b
        - qwen3:30b
```

The workflow sets no `condition` and no `on_error`: it always runs its four steps, and a failed step fails the job.

## Errors the loader catches

Voxtrama validates a workflow before it imports a recording or starts a job. Each message names the field's path. The command line prints them after `Invalid workflow: `, and the job form shows them the same way.

| Problem | Message |
|---|---|
| a field is missing or has the wrong type | `<file>: steps.0.skill_version: Field required` |
| `schema_version` is not `v1` | `<file>: schema_version: Input should be 'v1'` |
| a field the schema does not know, usually a typo | `<file>: steps.0.retries: Extra inputs are not permitted` |
| the file is not valid YAML or cannot be read | `<file>: ` followed by the YAML or system message |
| a step names a skill or version that does not exist | `steps[1].skill: unknown skill 'not_a_real_skill' version '1.0.0'` |
| `allows.skills` names a skill or version that does not exist | `steps[1].allows.skills[0]: unknown skill 'not_a_real_skill' version '1.0.0'` |
| `depends_on` names a step not in the workflow | `steps[1].depends_on: unknown step 'does_not_exist'` |
| `fallback_step` names a step not in the workflow | `steps[0].on_error.fallback_step: unknown step 'does_not_exist'` |
| steps depend on each other in a circle | `steps: dependency cycle: a -> b -> a` |
| a condition is not `<path> <operator> <literal>` | `steps[1].condition: malformed condition: '<text>'` |
| a condition names a path outside the list | `steps[1].condition: condition names a path outside the allowed list: 'this' in 'this is not a condition'` |
| a condition has no known operator | `steps[1].condition: condition has no recognised operator: '<text>'` |
| a condition has no literal after the operator | `steps[1].condition: condition has no literal after its operator: '<text>'` |
| the literal is not valid JSON | `steps[1].condition: condition literal is not valid JSON: '<text>'` |
| a condition reads a step that does not exist | `steps[1].condition: unknown step 'nope'` |
| the operator is not allowed on a step's state | `steps[1].condition: operator '>' is not valid on a step's state; use one of ['!=', '==', 'in', 'not in']` |
| the literal is not a state a step can reach | `steps[1].condition: 'done' is not a state a step can reach; use one of ['failed', 'skipped', 'succeeded']` |
| the step reads a state but does not depend on that step | `steps[1].condition: reads steps.<id>.state, but this step does not depend on '<id>'; add it to depends_on so it is guaranteed to run first` |
| a skill file did not load | the unknown-skill message, then `; that skill has a file that did not load: '<skill>' (<reason>)` |
| the name is not a valid name | `no workflow called '<name>': not a valid name` |
| no file with that name | `Unknown workflow: no workflow named '<name>' in: <data folder>/workflows, <the folders of the shipped workflows>` |
| more custom workflows than the edition allows | `Unknown workflow: workflow '<name>' is beyond the edition's custom limit` |

The Community Edition allows one custom workflow. A copy of a shipped workflow, saved under the same name in the data folder, replaces the shipped one and does not count as a custom workflow. When more custom workflows are on disk than the edition allows, the first one in alphabetical order is kept and the others are neither listed nor run.

## Run a workflow

```bash
docker compose exec web voxtrama run <workflow-name> /data/<file>
```

The command validates the workflow first. If the file does not pass, it prints one of the messages in the table, and nothing is imported or queued. [Command line](cli.md) lists the options, including `--detach` and `--reuse-from`.

A job that reuses an earlier job reuses it step by step. A step is reused when its recording, skill and choices match, and the first step that changed and every step after it are computed again. The `manifest.json` of the new job says which steps were reused and from which job.

When a job fails, its folder `<data folder>/runs/<job id>/` holds the evidence:

- `manifest.json` has a `failure` object with a `code`, a `message` and the step where it happened.
- `run.log` has every log line the worker wrote for the job, in order.

## Related pages

- [Workflows and skills](workflows.md)
- [Command line](cli.md)
- [Privacy and data](privacy.md)
- [Configuration](configuration.md)
