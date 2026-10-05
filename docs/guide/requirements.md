# Requirements

Voxtrama is a self-hosted tool that transcribes recordings, tells the speakers apart and turns the transcript into a recap whose every point carries a quote you can play back. It is local-first, and it needs a machine with enough memory and disk to run Whisper on the processor, plus Docker.

## Platforms

Voxtrama 0.1 has been tested end to end on macOS with an Intel processor. Linux and Apple Silicon have not been tested end to end yet. Windows is not supported yet.

| Platform | Status |
|---|---|
| macOS, Intel processor | Tested end to end |
| macOS, Apple Silicon | Not tested end to end yet |
| Linux | Not tested end to end yet |
| Windows | Not supported yet |

## Hardware

Voxtrama runs on the processor and needs memory and disk sized by the transcription profile you use. The profile picks the Whisper model.

| Profile | Whisper model | Memory it suits | Download |
|---|---|---|---|
| Low (**Efficient** in the guided setup) | small | 8 GB or less | 484 MB |
| Base (**Balanced**) | medium | between 8 GB and 32 GB | 1.5 GB |
| High (**Maximum accuracy**) | large-v3 | 32 GB or more | 3.0 GB |

- **Memory**: the figures are the thresholds Voxtrama itself uses to propose a profile, and the proposal only suggests: you can pick any profile that fits the disk. The guided setup estimates the memory of a configuration as the size of the model times the number of chunks transcribed in parallel, shows it under **Fine-tune** and warns when the numbers look too high for the machine.
- **Disk**: the transcription model (484 MB, 1.5 GB or 3.0 GB, one per profile you download) and the speaker model (83 MB) are downloaded once into the data folder. `voxtrama doctor` warns when less than 10 GiB is free where the data folder lives. Add the size of your recordings. An upload needs about three times its own size free in the data folder, or Voxtrama refuses it with a "Not enough room in the data folder" error.
- **Processor**: transcription is bound by the processor, so more cores help, and `voxtrama doctor` warns with fewer than 4 cores.
- **Graphics card**: not used. The Voxtrama image is built with the CPU version of PyTorch, and Docker on macOS cannot reach a graphics card anyway.
- **Summary model** (optional): a model served by Ollama needs roughly its own download size in memory, on top of what transcription uses. See [Set up the summary model](summary-model-setup.md).

## Software on the host

`make up` runs a small script on your machine before it calls Docker, so the host needs more than Docker.

| Requirement | Why |
|---|---|
| Docker with Compose | Runs the four containers: web server, worker, queue (Redis) and the one-off database step. Docker Desktop on macOS, Docker Engine with the Compose plugin on Linux. Use a recent Docker Compose v2: the project file uses `env_file` with `required: false` and `depends_on` with `service_completed_successfully`, which older releases reject. See the [Docker Compose documentation](https://docs.docker.com/compose/) to install or update it. |
| `make` | Runs `make up` and `make down`. |
| `python3` | `make up` uses it to find a free port. |
| `curl` | `make up` uses it to wait until the web server answers. |
| `git` | Gets the code from <https://github.com/sjpagan/voxtrama>. |
| A browser | Voxtrama is a web page on your own machine. |

Without `make`, `docker compose up -d` starts the same containers. See [Install on macOS](install-macos.md) or [Install on Linux](install-linux.md).

## Network

Voxtrama publishes its web page on `127.0.0.1` only, so nothing outside the machine can reach it. The network is needed for the downloads (the Whisper model, the speaker model, the Ollama models) and the first `docker compose` build. After that Voxtrama works offline, unless a job uses a remote model server.

## Example: measured times

Transcription takes a fraction of the audio length on the processor, and the summary model step varies a lot. These times are an example, not a promise.

| Audio | Transcription | Speaker diarization | Summary model steps | Total |
|---|---|---|---|---|
| 21 min 09 s, Italian | 7 min 30 s | 2 min 38 s | recap 1 min 47 s, concepts 2 min 46 s | 14 min 41 s |
| 16 min 00 s | 9 min 11 s | 1 min 19 s | recap 7 min 04 s, themes 5 min 58 s | 23 min 32 s |

Regenerating the first job with only the themes workflow reused the transcript and the speakers, and took 2 min 52 s. The profile was High (large-v3, 4 cores per chunk, 2 chunks in parallel), the summary model was `qwen3:4b` on Ollama on the host.

Measured in September 2026 with Voxtrama 0.1.0 on one machine, an Intel Xeon W-2150B with 64 GB of RAM.

## Related pages

- [Install on macOS](install-macos.md)
- [Install on Linux](install-linux.md)
- [Set up the summary model](summary-model-setup.md)
- [Configuration](configuration.md)
