<p align="center"><img src="src/voxtrama/web/static/img/logo-mark.png" alt="" width="136" height="96" /></p>

# Voxtrama

[![CI](https://img.shields.io/github/actions/workflow/status/sjpagan/voxtrama/ci.yml?branch=0.1.x&label=CI)](https://github.com/sjpagan/voxtrama/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sjpagan/voxtrama?include_prereleases&label=release)](https://github.com/sjpagan/voxtrama/releases)
[![License](https://img.shields.io/github/license/sjpagan/voxtrama)](LICENSE)

**From audio to verifiable knowledge.**

Voxtrama turns recordings you already have (meetings, lessons, interviews)
into a transcript with the speakers told apart, and then into a recap,
decisions, themes or key concepts. Every point it writes carries a quote
from the recording and the time it was said, so you can play the passage
and check it. It runs on your own machine, in Docker.

This is an alpha, `0.1.0-alpha2`: the whole path works on one machine,
and what is still missing is listed under [Status](#status).

## Contents

- [What it does, and for whom](#what-it-does-and-for-whom)
- [What it does not do, on purpose](#what-it-does-not-do-on-purpose)
- [Requirements](#requirements)
- [Install](#install)
- [First start and first job](#first-start-and-first-job)
- [Workflows](#workflows)
- [Privacy, data and retention](#privacy-data-and-retention)
- [Command line](#command-line)
- [Development](#development)
- [Documentation](#documentation)
- [Status](#status)
- [Branches and releases](#branches-and-releases)
- [Licence](#licence)

## What it does, and for whom

For people who record conversations they need to act on or study from,
and who cannot, or would rather not, send the audio to a cloud service:
teams keeping minutes, researchers coding interviews, students going over
a lesson.

- **Transcribes** audio with Whisper, on the machine's processor.
- **Tells the speakers apart** within one recording, and lets you name
  them in the job's Speakers tab.
- **Runs a workflow** on the transcript: a recap plus decisions, themes or
  concepts, written by a summary model served by
  [Ollama](https://ollama.com), on this machine or on another one you
  choose.
- **Ties every generated point to the audio.** A point whose quote cannot
  be found in the transcript is marked **Needs review** instead of being
  shown as fact.
- **Keeps a record of each job** (`manifest.json`): which models ran, with
  which settings, on which file. A job can be regenerated with other
  choices, reusing the steps whose inputs did not change.
- **Deletes what is no longer needed**, by hand or after a retention
  period.

## What it does not do, on purpose

- **It does not remember voices.** Speakers are told apart inside one
  recording. No voice print is kept to recognise the same person in the
  next one. A voice print is biometric data, and holding it would
  turn a transcription tool into an identification system.
- **It does not download audio from other sites.** It transcribes files
  you already have. Fetching recordings from video platforms is scraping
  under terms of service we do not control.
- **It does not use a graphics card.** Docker on macOS cannot reach one,
  and transcription runs on the processor everywhere. A summary model can
  use one if its Ollama server has it.

## Requirements

| | |
|---|---|
| **Platform** | macOS (tested end to end on an Intel processor) or Linux (not tested end to end yet). Apple Silicon has not been tested end to end yet. Windows is not supported yet |
| **Docker** | Docker Desktop on macOS, or Docker Engine with the Compose plugin on Linux |
| **Memory** | 8 GB or less suits the smallest model, between 8 and 32 GB the medium one, 32 GB or more the most accurate. A summary model needs roughly its own download size on top |
| **Disk** | about 0.6 GB for the smallest transcription model and the speaker model, up to 3 GB more for the most accurate one, plus your recordings |
| **Port** | one free local port. `make up` starts from 8000 and takes the first free one |
| **Summary model** (optional) | Ollama with at least one model pulled. Transcription works without it |

## Install

```bash
git clone https://github.com/sjpagan/voxtrama.git
cd voxtrama
cp .env.example .env
make up
```

Nothing in `.env` needs editing before the first start. `make up` starts four
containers in order (the Redis queue, a one-off database migration, then
the web server and the worker), waits until the web server answers, and
prints the address, for example `http://127.0.0.1:8000`.
`docker compose up -d` starts the same containers on port 8000 without
waiting.

Everything Voxtrama keeps lives in one folder on the host, `~/Voxtrama` by
default: recordings, results, models, the database and the settings file.
Set `VOXTRAMA_DATA_DIR` in `.env` to move it. The files in it belong to the
folder's owner, so you can delete them without `sudo`.

```bash
make down                  # stop
docker compose down -v     # remove the containers
rm -rf ~/Voxtrama          # and every file Voxtrama wrote
```

The variables `.env` accepts are listed in
[Configuration](docs/guide/configuration.md). To use a summary model,
pull one in Ollama and name it in `.env`:

```bash
ollama pull qwen3:4b
echo 'VOXTRAMA_OLLAMA_MODEL=qwen3:4b' >> .env
make down && make up
```

[Summary models and servers](docs/guide/model-servers.md) covers a remote
server, credentials, and several servers at once.

## First start and first job

1. Open the address `make up` printed. The home page proposes a profile
   for this machine: the transcription model, and how many cores it uses.
2. Press **Download the transcription model** (484 MB on the smallest
   profile). It is downloaded once, into the data folder.
3. Drop one or more audio files on the **Audio** card. WAV, FLAC, MP3,
   M4A and OGG all work. Several files can be joined one after another,
   or mixed as separate microphones recorded together.
4. Pick a workflow, and optionally the recap's language and detail, then
   press **Start job**. The first job also downloads the speaker model
   (83 MB).
5. Follow the job live: each step, its progress and its log lines.
6. Read the result: the recap with each point linked to the moment it
   was said, the transcript, and the Speakers tab to name the voices.

The guide has a page for each step:
[First start](docs/guide/first-start.md),
[Start a job](docs/guide/new-job.md),
[Follow a job](docs/guide/follow-a-job.md),
[The job page](docs/guide/job-page.md).

## Workflows

| Workflow | What it produces |
|---|---|
| `transcribe-only` | the transcript, with its speakers |
| `meeting-decisions` | a recap, and decisions with an owner, a deadline and a supporting quote |
| `lesson-companion` | a recap, and the key concepts with their definitions |
| `research-interview` | a recap, and themes, each with a supporting quote |

Every workflow except `transcribe-only` needs a summary model. A workflow
is a YAML file under `workflows/`, and a new one needs no code. See
[Workflows](docs/guide/workflows.md) and
[Workflow files](docs/guide/workflow-files.md).

## Privacy, data and retention

- The audio and the transcript stay on this machine unless a job is sent
  to a remote model server that you configured. **Settings › Data &
  privacy** shows, for each step of each workflow, where it runs.
- A step marked `local_only` refuses to run on a remote server.
- A credential for a model server is sent only over `https`, or to a
  server on this machine.
- The app listens on `127.0.0.1` and refuses requests coming from other
  sites or other host names.
- **Retention** deletes finished jobs after 7, 30, 90 or 365 days, or
  never (the default). A job can ask to be kept for less time, never for
  more.
- **Clean up** removes failed jobs and unused recordings older than a
  week.

Details: [Settings](docs/guide/settings.md),
[Jobs and retention](docs/guide/jobs.md),
[Taking your data with you](docs/guide/data-portability.md).

## Command line

The CLI runs inside the container, where the database and the data folder
are:

```bash
docker compose exec web voxtrama doctor          # check the installation
docker compose exec web voxtrama demo            # run the shipped sample
cp meeting.wav ~/Voxtrama/
docker compose exec web voxtrama run transcribe-only /data/meeting.wav
docker compose exec web voxtrama compare /data/runs/<id-a> /data/runs/<id-b>
```

`doctor` is the first thing to run, and to paste, when something does not
work. Every command and option: [Command line](docs/guide/cli.md).

## Development

Install from the lock files, which pin every library the image and the
tests use:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps -e .
```

Lint and test. The suite runs in-process, with no Redis and no network:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Some tests need a private evaluation set of real recordings, never part of
this repository. Point `VOXTRAMA_EVAL_DIR` at it to run them. Without it
they are skipped ([The evaluation set](docs/evaluation-set.md)).

The stylesheet is built from Sass under `src/voxtrama/web/scss/`. Edit
those, never `static/css/voxtrama.min.css`. CI fails if the committed CSS
does not match the sources.

```bash
make sass-install   # once: the locked dart-sass, into .tools/
make css
```

`make lock` regenerates both lock files from the ranges in
`pyproject.toml`: run it when a dependency changes, then `make licences`
to update `THIRD_PARTY_LICENSES.md`, and commit the three files together
with the tests green. `make docs` builds the user guide
with MkDocs, and `make docs-serve` serves it locally.
The same guide is mirrored, read-only, in the GitHub wiki, generated from
`docs/guide` by `.github/workflows/wiki.yml`.

For live reload, the development overlay runs `uvicorn --reload` with
`src/` mounted. The worker does not reload, so restart it after changing
worker code:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up
docker compose -f compose.yaml -f compose.dev.yaml restart worker
```

Every process logs one JSON object per line to `stdout`. Lines from a job
also go to `<data folder>/runs/<id>/run.log`.

## Documentation

The user guide is online at <https://sjpagan.github.io/voxtrama/>, built from
`docs/guide/` on every change to the `0.1.x` branch.

| Document | What it covers |
|---|---|
| [User guide](docs/guide/index.md) | installing and using Voxtrama, page by page. `make docs` builds it |
| [Configuration](docs/guide/configuration.md) | every variable in `.env` |
| [Troubleshooting](docs/guide/troubleshooting.md) | what to check when something does not work |
| [Translating Voxtrama](docs/translating.md) | how to add a language |

## Status

Works today: upload, local transcription, speakers told apart and named,
the four workflows with every point tied to the audio, live progress,
stopping a job, comparing and regenerating jobs, deletion and retention.

Not there yet: the measurements that stop a release from getting worse
without a test saying so. Until 1.0 there is no compatibility promise: an
update may change the shape of workflow files and of stored jobs, and the
release notes say so when it does. Voxtrama was written from scratch. It
is not a fork or a rename of an earlier project.

## Branches and releases

Voxtrama follows the model of Drupal.org projects: one development branch
per release series, and tags that say how stable a release is.

| Branch | Holds |
|---|---|
| `0.1.x` | the 0.1 series. The default branch |

A series that breaks compatibility gets its own branch (`0.2.x`, then
`1.0.x`), and the previous one keeps receiving fixes only. Changes arrive
as pull requests against the series branch. Nobody pushes to it directly.

Releases are tagged `0.1.0-alpha1`, `0.1.0-beta1`, `0.1.0-rc1`, `0.1.0`,
then `0.1.1` for fixes. Alpha, beta and release-candidate tags are
published as pre-releases. Python writes the same versions as `0.1.0a1`,
`0.1.0b1`, `0.1.0rc1`.

## Licence

Released under the [Apache License 2.0](LICENSE) © 2026 Giorgio Alfredo Pagano.
Keep the [NOTICE](NOTICE) file in every copy and every derivative work. The
licence does not cover the name "Voxtrama". The libraries Voxtrama uses and
the models it downloads keep their own licences, listed in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and shown before each
model download.
