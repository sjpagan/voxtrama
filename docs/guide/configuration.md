# Configuration

Voxtrama reads its settings from three places, strongest first:

1. **`.env`**, next to `compose.yaml`. `make up` and `docker compose` pass
   it to every container.
2. **`voxtrama.toml`**, in the data folder, written by the first start and
   by the Settings pages.
3. The built-in defaults.

A value set in `.env` wins over the file, and the Settings pages mark it
**from environment**. Change `.env`, then restart with `make down` and
`make up`.

## Data folder

Everything Voxtrama keeps lives in one folder, `~/Voxtrama` unless
`VOXTRAMA_DATA_DIR` says otherwise:

```
~/Voxtrama/
├── recordings/<id>/     # the audio you imported, and the copies made from it
├── runs/<job id>/       # one folder per job: manifest.json, output.json, run.log
├── models/              # downloaded model weights
├── workflows/           # your custom workflows
├── voxtrama.toml        # the installation's settings
└── voxtrama.db          # the database
```

A recording's folder holds, next to the file you gave:

| File | What it is |
|---|---|
| `resampled_16k.wav` | a 16 kHz mono copy, made only when the original is another format |
| `cleaned_16k_v1.wav` | the filtered, levelled copy the transcription reads |
| `peaks-v3.json` | the levels the player draws its waveform from |

A job's folder can also hold `edits.json`, the corrections made by hand to
its verified output (see [The job page](job-page.md#correct-a-point)).

Nothing is kept inside the containers. [Taking your data with
you](data-portability.md) says what to copy to another machine.

## Variables

All of them are optional. `.env.example` lists them, commented out.

### Where and as whom

| Variable | Default | What it does |
|---|---|---|
| `VOXTRAMA_DATA_DIR` | `~/Voxtrama` | the data folder on your machine; an absolute path |
| `VOXTRAMA_HOST_PORT` | `8000` | the port on your machine the app answers on |
| `VOXTRAMA_RUN_AS_UID`, `VOXTRAMA_RUN_AS_GID` | the data folder's owner | the user and group Voxtrama writes as |
| `VOXTRAMA_ALLOWED_HOSTS` | `["127.0.0.1", "localhost", "::1"]` | the addresses the app answers to; add one only if you open Voxtrama through another name |

### Transcription

| Variable | Default | What it does |
|---|---|---|
| `VOXTRAMA_HARDWARE_PROFILE` | the machine's proposal | `low` (Whisper small), `base` (medium) or `high` (large-v3) |
| `VOXTRAMA_CORES_PER_CHUNK`, `VOXTRAMA_PARALLEL_CHUNKS` | the machine's proposal | how many cores a job uses |
| `VOXTRAMA_MAX_SPEAKERS` | `4` | the most voices diarisation tells apart |
| `VOXTRAMA_MAX_UPLOAD_MB` | `8192` | the largest upload the new-job form accepts |

### Summary model

| Variable | Default | What it does |
|---|---|---|
| `VOXTRAMA_OLLAMA_URL` | Ollama on this machine | the model server's address |
| `VOXTRAMA_OLLAMA_MODEL` | none | the summary model |
| `VOXTRAMA_OLLAMA_AUTH` | none | a credential: `user:password` for Basic, anything else as a Bearer token; sent only over `https` to a remote server |
| `VOXTRAMA_PROVIDERS` | none | several servers, as JSON |
| `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` | `1800` | how long one call to the model may take |
| `VOXTRAMA_PARALLEL_WINDOWS` | `2` | how many parts of a long transcript go to the model at the same time |

[Summary models and servers](model-servers.md) explains each of them.

### Defaults of the new-job form

| Variable | Default | What it does |
|---|---|---|
| `VOXTRAMA_SUMMARY_DETAIL` | `3` | the detail level, 1 to 5 |
| `VOXTRAMA_PAUSE_MERGE_SECONDS` | `1.5` | «Merge pauses under» in the Transcript tab |
| `VOXTRAMA_RETENTION_DAYS` | none | delete finished jobs after this many days |
| `VOXTRAMA_DEFAULT_LOCALE` | the browser's | the interface language when the browser asks for none Voxtrama has |

### Logs

| Variable | Default | What it does |
|---|---|---|
| `VOXTRAMA_LOG_LEVEL` | `INFO` | `DEBUG` for more detail in `docker compose logs` |
