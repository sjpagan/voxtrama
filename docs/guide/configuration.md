# Configuration

Voxtrama reads its settings from four sources. When two sources set the same value, the stronger one wins.

| Order | Source | Where it lives | Written by |
|---|---|---|---|
| 1 | environment variables | `.env` next to `compose.yaml`, passed to every container by `make up` and `docker compose` | you |
| 2 | `voxtrama.toml` | the data folder | the guided setup, the Settings pages, or you by hand |
| 3 | `proposal.toml` | the data folder | Voxtrama, as the proposal for this machine |
| 4 | built-in defaults | the code | nobody |

`proposal.toml` is read only while `voxtrama.toml` does not exist. It holds the hardware profile and the two core counts proposed for the machine. The first job, or the guided setup, writes `voxtrama.toml` with the values that were used, and from then on `proposal.toml` is no longer in force. A `voxtrama.toml` that cannot be parsed is treated as absent.

A value set in the environment wins over the file. The Settings pages mark such a value **from environment**, and saving it there has no effect until the variable changes or is removed. After editing `.env`, restart with `make down` and `make up`.

A value that fails validation stops the start-up, and the message names the variable.

## Data folder

Everything Voxtrama keeps lives in one folder. With the `compose.yaml` shipped in the repository, the folder is `~/Voxtrama` unless `VOXTRAMA_DATA_DIR` says otherwise. Inside the containers the folder is always `/data`.

```
~/Voxtrama/
├── recordings/<id>/     # the audio you imported, and the copies made from it
├── runs/<job id>/       # one folder per job: manifest.json, output.json, run.log
├── models/              # downloaded model weights
├── logs/                # created at start-up
├── workflows/           # your custom workflows, created with the first one
├── voxtrama.toml        # the installation's settings
├── proposal.toml        # the proposal for this machine, until voxtrama.toml exists
└── voxtrama.db          # the database
```

The container's start-up script creates `recordings/`, `runs/`, `models/` and `logs/` when they are missing. Voxtrama does not write into `logs/` in this version; each job's log is its `run.log`.

A recording's folder holds the file you gave, unchanged, and the copies made from it:

| File | What it is |
|---|---|
| `resampled_16k.wav` | a 16 kHz mono copy, made when the original is not already a 16 kHz mono WAV |
| `cleaned_16k_v1.wav` | the filtered, levelled copy the transcription reads |
| `peaks-v3.json` | the levels the player draws its waveform from |

A job's folder holds `manifest.json`, `output.json` and `run.log`. It also holds `edits.json` once you have corrected a point by hand.

Nothing is kept inside the containers. [Taking your data with you](data-portability.md) says what to copy to another machine.

## Environment variables

Every variable is optional and starts with `VOXTRAMA_`. `.env.example` lists them commented out. Lists and objects are written as JSON.

### Where, and as whom

| Variable | Default | Range or format | What it does |
|---|---|---|---|
| `VOXTRAMA_DATA_DIR` | `~/Voxtrama` | an absolute path | the data folder on your machine; `compose.yaml` does not expand `~` in a value you set |
| `VOXTRAMA_HOST_PORT` | `8000` | a port number | the port on your machine the app answers on; the container always listens on 8000 |
| `VOXTRAMA_RUN_AS_UID`, `VOXTRAMA_RUN_AS_GID` | the owner of the data folder | numeric ids | the user and group Voxtrama writes as, for network mounts and service accounts |
| `VOXTRAMA_ALLOWED_HOSTS` | `["127.0.0.1", "localhost", "::1"]` | JSON list of names | the host names the app answers to; any other gets `Forbidden: unknown host.` |
| `VOXTRAMA_MODELS_DIR` | `<data folder>/models` | a path | where model weights are stored |
| `VOXTRAMA_DATABASE_URL` | `sqlite:///<data folder>/voxtrama.db` | a database URL | the database |
| `VOXTRAMA_QUEUE_URL` | `redis://localhost:6379/0` | a Redis URL | the job queue; `compose.yaml` sets it to the `redis` container |
| `VOXTRAMA_EVAL_DIR` | none | a path | the folder `voxtrama calibrate` reads; see [Command line](cli.md) |
| `VOXTRAMA_LOG_LEVEL` | `INFO` | a Python log level, for example `DEBUG` | the detail in `docker compose logs` |
| `VOXTRAMA_EXTRA_ROOTS` | none | none | listed in `.env.example` but not implemented in 0.1; setting it has no effect |

Outside the `compose.yaml` shipped in the repository, the data folder defaults to `~/Library/Application Support/voxtrama` on macOS and `~/.local/share/voxtrama` on Linux. `VOXTRAMA_HOST_PORT` is read by `compose.yaml`. `make up` also reads it from `.env`; when it is not set, `make up` picks the first free port from 8000 upward and prints the address.

### Transcription

| Variable | Default | Range or format | What it does |
|---|---|---|---|
| `VOXTRAMA_HARDWARE_PROFILE` | the proposal, else `base` | `low`, `base` or `high` | the Whisper model: `low` is small, `base` is medium, `high` is large-v3 |
| `VOXTRAMA_CORES_PER_CHUNK` | the proposal for this machine | a whole number, at least 1 | the processor cores each chunk of audio uses |
| `VOXTRAMA_PARALLEL_CHUNKS` | the proposal for this machine | a whole number, at least 1 | how many chunks of audio are transcribed at the same time |
| `VOXTRAMA_MAX_SPEAKERS` | `4` | a whole number, at least 1 | the most voices speaker diarization tells apart |
| `VOXTRAMA_MAX_UPLOAD_MB` | `8192` | a whole number, at least 1 | the largest upload the new-job form accepts; the limit applies to the whole request, so several files count together |

A single job can carry its own `max_speakers`, `cores_per_chunk` and `parallel_chunks` in its choices, and they win over the installation's values for that job only. The new-job form has fields for the two core counts and none for `max_speakers`: no page sets it per job, so the installation's value applies.

### Summary model

| Variable | Default | Range or format | What it does |
|---|---|---|---|
| `VOXTRAMA_OLLAMA_URL` | none | an `http` or `https` address without credentials | the model server; the guided setup proposes `http://host.docker.internal:11434` |
| `VOXTRAMA_OLLAMA_MODEL` | none | a model name, for example `qwen3:4b` | the summary model |
| `VOXTRAMA_OLLAMA_AUTH` | none | `user:password` or a token | the credential: Basic with a colon, Bearer otherwise; sent only over `https`, or to a server on this machine |
| `VOXTRAMA_PROVIDERS` | none | JSON object of named servers | several model servers; replaces `VOXTRAMA_OLLAMA_URL` and `VOXTRAMA_OLLAMA_AUTH` |
| `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` | `1800` | seconds | how long one call to the summary model may take |
| `VOXTRAMA_PARALLEL_WINDOWS` | `2` | 1 to 16 | how many parts of a long transcript go to the model at the same time |

An address that carries a credential, such as `https://user:secret@host`, is refused at start-up. [Summary models and servers](model-servers.md) explains each variable.

### Defaults of the new-job form

| Variable | Default | Range or format | What it does |
|---|---|---|---|
| `VOXTRAMA_SUMMARY_DETAIL` | `3` | 1 to 5 | the **Summary detail** level a new job starts with |
| `VOXTRAMA_PAUSE_MERGE_SECONDS` | `1.5` | 0.1 to 10 | the **Pause merge** a new job starts with; the form's slider covers 0.5 to 5 seconds |
| `VOXTRAMA_RETENTION_DAYS` | none, so finished jobs are kept | 1 to 36500 | delete finished jobs after this many days |
| `VOXTRAMA_DEFAULT_LOCALE` | none | a language code | the interface language used when the browser's `Accept-Language` offers none Voxtrama has; without it, English |

The interface language is chosen in this order: the browser's `Accept-Language`, then `VOXTRAMA_DEFAULT_LOCALE`, then English.

### Set by compose, not by you

`compose.yaml` sets these for its services. They are listed so you recognise them in the output of `docker compose config`.

| Variable | Value in `compose.yaml` | What it does |
|---|---|---|
| `VOXTRAMA_DATA_DIR` | `/data` | the data folder inside the container |
| `VOXTRAMA_HOST_DATA_DIR` | the folder on your machine | lets the setup pages show the folder as you typed it |
| `VOXTRAMA_QUEUE_URL` | `redis://redis:6379/0` | the queue, in the `redis` container |
| `VOXTRAMA_HARDWARE_PROFILE` | empty unless set on the host | passed through, so that all three containers read the same value |
| `HF_HUB_DISABLE_PROGRESS_BARS` | `1` | keeps download bars out of the worker's log; Voxtrama reports download progress itself |

`VOXTRAMA_PROFILE`, `VOXTRAMA_HOST` and `VOXTRAMA_PORT` exist in the code and are not used by the application in 0.1. Leave them unset.

## voxtrama.toml

`voxtrama.toml` is plain text that you can edit by hand and copy to another machine. Removing it makes the next visit a first start.

| Key | Type | What it holds |
|---|---|---|
| `hardware_profile` | `"low"`, `"base"` or `"high"` | the transcription profile |
| `cores_per_chunk` | whole number, at least 1 | cores per chunk |
| `parallel_chunks` | whole number, at least 1 | chunks in parallel |
| `ollama_model` | text | the summary model |
| `ollama_url` | text | the address of the model server that answered at setup |
| `retention_days` | whole number, 1 to 36500 | the installation's retention limit |
| `instance_token` | text | a random token the guided setup generates and keeps when settings are saved; this version does not use it |
| `[model_context_limits]` | table of model name to number | the context window measured for each model at setup, which **Use at most** can only lower |

Only the keys that match a setting are read as settings. `model_context_limits` and `instance_token` are read by the setup code.

A file with example values:

```toml
hardware_profile = "high"
cores_per_chunk = 4
parallel_chunks = 2
ollama_model = "qwen3:4b"
ollama_url = "http://host.docker.internal:11434"

[model_context_limits]
"qwen3:4b" = 8192
```

## Related pages

- [Command line](cli.md)
- [Summary models and servers](model-servers.md)
- [Settings pages](settings.md)
- [Taking your data with you](data-portability.md)
