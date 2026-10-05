# Command line

The `voxtrama` command runs inside the `web` container, where the database and the data folder are. Every command is called through `docker compose exec web`, from the folder that holds `compose.yaml`:

```bash
docker compose exec web voxtrama <command>
```

!!! note "File paths"
    The container sees only the data folder, mounted as `/data`. A file passed to `run` must therefore be inside the data folder and named by its path in the container. With the default data folder, `~/Voxtrama/meeting.wav` on your machine is `/data/meeting.wav` in the container. If `VOXTRAMA_DATA_DIR` points elsewhere, that folder still appears as `/data`.

!!! note "Which user runs the command"
    `docker compose exec` starts the command as the image's default user. The web server and the worker run as the `voxtrama` user, which the container's start-up script aligns with the owner of the data folder. `docker compose exec -u voxtrama web voxtrama <command>` runs a command as that user. The image sets no other user, and the start-up script that aligns ownership is bypassed by `exec`, so a plain `exec` runs as root and the files it writes into the data folder are owned by root. Use `-u voxtrama` for `run` and `demo`.

## Commands

| Command | What it does |
|---|---|
| `voxtrama doctor` | measures the installation and reports what to set |
| `voxtrama demo` | runs the bundled sample recording |
| `voxtrama run <workflow> <file>` | imports a file and runs a workflow on it |
| `voxtrama compare <a> <b>` | compares the manifests of two jobs |
| `voxtrama retention` | lists the jobs retention emptied and checks that nothing of them is left |
| `voxtrama correct <recording id>` | corrects the title or the source address of a recording |
| `voxtrama calibrate` | reports whether the private evaluation set is in place |
| `voxtrama version` | prints the installed version |

`voxtrama --help` lists the commands, and `voxtrama <command> --help` lists the options of one command.

## doctor

```bash
docker compose exec web voxtrama doctor
```

The command prints up to six sections: **Machine**, **Data directory**, **Queue**, **Hardware profile**, **Generative models** and **Generative provider**.

| Section | What it reports |
|---|---|
| **Machine** | platform and architecture, CPU, cores, memory, accelerator |
| **Data directory** | path, free space, the user the process runs as, the owner of the folder, and a write test that creates and removes a real file |
| **Queue** | the queue address and whether it answers |
| **Hardware profile** | the configured profile, the suggested one, and the `.env` line that would apply it |
| **Generative models** | whether the recommended summary models fit in the memory of this machine |
| **Generative provider** | the model server's host, whether it is local or remote, its latency, its version, its models, and the speed of a timed generation |

The command suggests and never applies: it prints the line to put in `.env` and leaves the choice to you.

| Option | What it does |
|---|---|
| `--no-measure` | skips the timed generation on the model server |

Paste the output of `doctor` when you ask for help. It never contains a model server credential.

## demo

```bash
docker compose exec web voxtrama demo
```

The command runs the sample recording shipped in the image through the `transcribe-only` workflow and follows the job to its end. The sample has two speakers and lasts about thirteen seconds. The command first prints `Running the 'transcribe-only' workflow on the bundled sample (public-fixture.wav): two speakers, about thirteen seconds.` and then the same progress lines as `run`. The first run downloads the transcription model and the speaker model.

The command takes no options and exits like `run`.

## run

```bash
cp meeting.wav ~/Voxtrama/
docker compose exec web voxtrama run transcribe-only /data/meeting.wav
```

The command checks the file and the workflow, imports the file, starts a job and follows it to its end. The job appears in the Jobs page like a job started from the browser. The command prints the job id first, then the progress of each step.

Before it starts the job, the command announces what to expect: the download size when models are missing, and the expected processing time for the length of the audio.

| Argument or option | What it does |
|---|---|
| `<workflow>` | the name of the workflow, which is the file name without `.yaml` (see [Workflow files](workflow-files.md)) |
| `<file>` | the path of the audio or video file, inside the container |
| `--detach` | prints the job id and returns at once, without following the job |
| `--reuse-from <job id>` | reuses the steps of that job whose inputs did not change |

With `--reuse-from`, a step is reused when its recording, skill and choices match the earlier job. The first step that changed is computed again, and so is every step after it.

## compare

```bash
docker compose exec web voxtrama compare /data/runs/<job a> /data/runs/<job b>
```

The command compares two manifests and reports the differences that count: another model, other settings, another input file. Each argument is a job folder, which holds a `manifest.json`, or a manifest file. Identifiers and times, which change on every job, are left out of the report and counted in one line.

| Option | What it does |
|---|---|
| `--show-expected` | lists the ignored differences too |

The report starts with `Differences that count:` followed by one line per difference, or reads `No differences that count.` when there are none. When the two manifests have a different `manifest_version`, that is the only difference reported.

## retention

```bash
docker compose exec web voxtrama retention
```

The command prints the installation's limit (`Installation limit: 30 days` or `Installation limit: none`). It then lists every job whose content retention deleted, with the date, the limit and the level that set the limit, and states for each job either `nothing left` or `LEFT:` followed by what remains. When no job was deleted, it prints `No job has been deleted by retention.`

The command takes no options.

## correct

```bash
docker compose exec web voxtrama correct <recording id> --label "Weekly sync, 26 September"
```

The command corrects the title (`--label`) or the source address (`--url`) stored for a recording, and prints the recording with its new values. Jobs started afterwards see the correction. The manifests of jobs already run keep what they ran with.

The recording id is the name of the recording's folder under `recordings/` in the data folder.

| Option | What it does |
|---|---|
| `--label <text>` | the corrected title |
| `--url <address>` | the corrected source address |

Only recordings imported before the import from an address was removed carry a title and a source address.

## calibrate

```bash
docker compose exec web voxtrama calibrate
docker compose exec web voxtrama calibrate --run <job id>
```

Without an option, the command reports whether the private evaluation set is in place. The set is a folder of real recordings that you provide, and `VOXTRAMA_EVAL_DIR` points at it. Voxtrama never ships real audio. The command prints one of these cases, and every case exits with `0`:

| Case | What the report says |
|---|---|
| variable not set | `VOXTRAMA_EVAL_DIR is not set.` |
| folder missing | `VOXTRAMA_EVAL_DIR is set to <path>, but that path does not exist.` |
| no `reference.csv` | `No reference.csv here yet: this is raw material, not a curated corpus.` |
| `reference.csv` with other columns | the expected columns and the columns found |
| clips without annotation files | the list of clips, each with `clip:` and `annotation:` |
| annotated clips | the path, the revision, the number of clips and `annotated: N of M` |

The command does not yet measure extraction against the set.

| Option | What it does |
|---|---|
| `--run <job id>` | reports the anchoring measures of that job instead: for each step and each skill, the number of claims, how many need review, the coverage and whether the result is deterministic |

With `--run`, a job without `manifest.json` or `output.json` gets a line saying which file is missing.

## version

```bash
docker compose exec web voxtrama version
```

The command prints the installed package version, for example `0.1.0a2`.

## Exit codes

| Command | Code | When |
|---|---|---|
| any | `2` | a value in the environment or in `voxtrama.toml` is invalid; the message names the variable |
| `run`, `demo` | `0` | the job finished, or `--detach` returned |
| `run`, `demo` | `0` | no worker picked the job up within 30 seconds; the command prints `Still queued: no worker has picked it up. The run is not lost.` |
| `run`, `demo` | `1` | the job failed, or the file, the workflow, the media or the data folder is refused (see the messages table) |
| `doctor` | `0` | the report was printed |
| `doctor` | `1` | the write test on the data folder failed |
| `compare` | `0` | no difference counts |
| `compare` | `1` | at least one difference counts |
| `compare` | `2` | a manifest cannot be read or does not match the schema |
| `retention` | `0` | nothing is left of the deleted jobs, or no job was deleted |
| `retention` | `1` | something is left of a deleted job |
| `correct` | `1` | no option was given, or the recording does not exist |
| `calibrate`, `version` | `0` | always |

## Messages

| Message | Command | Cause and fix |
|---|---|---|
| `Audio file not found: <path>` | `run` | the path does not exist in the container; copy the file into the data folder and use its `/data/...` path |
| `Unknown workflow: no workflow named '<name>' in: <folders>` | `run` | no file `<name>.yaml` in the `workflows/` folder of the data folder or among the shipped workflows |
| `Invalid workflow: <path>: <field>: <reason>` | `run` | the file does not pass validation; see [Workflow files](workflow-files.md) |
| `Unsupported media: <file> is not an audio or video file` | `run` | the container format is not accepted |
| `Unsupported media: <file> has no audio stream` | `run` | the file has no audio track |
| `Unsupported media: ffprobe could not determine the duration of <file>` | `run` | the duration cannot be read from the file |
| `Unknown run to reuse from: <id>` | `run` | the id given to `--reuse-from` is not a job; nothing was imported |
| `VOXTRAMA_DATA_DIR points at <path>, which does not exist.` | `run` | create the folder, or change the variable in `.env` |
| `VOXTRAMA_DATA_DIR points at <path>, which is a file, not a directory.` | `run` | point the variable at a folder |
| `VOXTRAMA_DATA_DIR points at <path>, which this process cannot write to.` | `run` | run `voxtrama doctor` to see which user does not match |
| `Demo audio missing: ...` | `demo` | the sample is missing from the image; rebuild the image |
| `Nothing to correct: pass --label and/or --url.` | `correct` | give at least one option |
| `no recording with id '<id>'` | `correct` | the id is not a folder under `recordings/` |
| `cannot read <path>: ...` or `invalid JSON in <path>: ...` | `compare` | the manifest is missing or damaged |

## Related pages

- [Configuration](configuration.md)
- [Workflow files](workflow-files.md)
- [Check the installation](check-installation.md)
- [Troubleshooting](troubleshooting.md)
