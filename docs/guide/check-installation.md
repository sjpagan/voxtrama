# Check the installation

The `voxtrama doctor` command checks that an installation works: it reports what the machine offers, whether the data folder can be written, whether the queue answers and whether a summary model server is reachable. It suggests settings and never changes them.

## Run doctor

1. Run:

    ```bash
    docker compose exec -u voxtrama web voxtrama doctor
    ```

    You should see the sections Machine, Data directory, Queue, Hardware profile, Generative models and Generative provider, in that order.

2. Check the exit code if you run it from a script:

    ```bash
    echo $?
    ```

    You should see `0` when the data folder can be written, and `1` when the write test failed.

The `-u voxtrama` option makes the command run as the user the application runs as. Without it, `docker compose exec` runs as root, a root process can write almost anywhere, and the write test passes even when the application itself could not write. The image sets no user, and the entrypoint switches to `voxtrama` only for the main process.

Doctor is the first thing to run, and to paste into a question, when something does not work.

## Skip the speed measurement

Doctor times a real generation on the summary model server, and that takes time. To skip it:

```bash
docker compose exec -u voxtrama web voxtrama doctor --no-measure
```

You should see `speed:        skipped (--no-measure)` in the Generative provider section.

## What each line means

### Machine

| Line | Meaning |
|---|---|
| `platform` | Operating system and architecture, with "(in a container)" inside Docker. |
| `CPU` | The processor name, or `unknown`. |
| `CPU cores` | A count, or a performance plus efficiency split where the platform reports one. Inside Docker Desktop, the cores Docker Desktop allocates. |
| `memory` | Physical memory visible to the container, with "(unified with GPU)" where it applies. Inside Docker Desktop, the memory Docker Desktop allocates. |
| `accelerator` | A graphics chip if one is detected, or `none detected`. |

### Data directory

| Line | Meaning |
|---|---|
| `path` | The data folder as the application sees it. Inside the container it is `/data`. |
| `exists` | `yes` or `no`. |
| `free space` | Free disk space where the folder lives. |
| `process uid` | The user and group the process runs as. |
| `owned by` | The user and group that own the folder. |
| `write test` | `ok (a file was created and removed)`, or `FAILED:` with the reason and what to do. A failed test makes doctor exit with code 1. |

When the write test fails, doctor says either that the folder does not exist, or to make the folder writable by the process uid, or to set `VOXTRAMA_RUN_AS_UID` to the owner uid in `.env` and restart.

### Queue

| Line | Meaning |
|---|---|
| `url` | The queue address, `redis://redis:6379/0` inside Docker. |
| `reachable` | `yes`, or `NO:` with the error and how to start the queue. |

### Hardware profile

Before the Hardware profile section, doctor can print warnings that start with `!`: less than 10 GiB free where the data folder lives, fewer than 4 CPU cores, and a visible graphics card that Voxtrama 0.1 does not use.

| Line | Meaning |
|---|---|
| `configured` | The profile in force: `low`, `base` or `high`. |
| `suggested` | The profile that fits the memory, with the reason, or `none` when memory could not be read. |

When the suggestion differs from the profile in force, doctor prints the `VOXTRAMA_HARDWARE_PROFILE=` line to put in `.env`. It never applies it.

### Generative models

One line per entry of a declared table of summary models, with `fits` or `does not fit` and the memory margin in GiB. The margin assumes nothing else is loaded, not while transcribing. When none fits, doctor says to use a remote server or skip the generative steps.

### Generative provider

| Line | Meaning |
|---|---|
| `name` | The server name and whether it is local or remote. |
| `host` | The server address. |
| `reachable` | `yes (latency: N ms)`, or `NO:` with the error. |
| `version` | The Ollama version, and whether it meets the minimum Voxtrama needs. |
| `models` | The models present, with sizes. |
| `speed`, `model load`, `generation` | A timed generation on the smallest model present: model load time and tokens per second. |

With no server configured, doctor prints `no generative provider is configured` and the line to put in `.env`. See [Set up the summary model](summary-model-setup.md).

## Check in the browser

The chip at the top right of every page summarises the same checks. See [First start](first-start.md) for its states.

## Related pages

- [First start](first-start.md)
- [Command line](cli.md)
- [Set up the summary model](summary-model-setup.md)
- [Troubleshooting](troubleshooting.md)
