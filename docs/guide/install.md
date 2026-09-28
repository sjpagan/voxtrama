# Install

Voxtrama runs as four Docker containers on one machine: a web server, a
worker that processes jobs, a queue (Redis) and a one-off step that
prepares the database. You need Docker and a copy of the repository.

## What you need

| | |
|---|---|
| **Docker** | Docker Desktop on macOS or Windows, or Docker Engine with the Compose plugin on Linux. |
| **Memory** | 8 GB is enough for transcription with the smallest model. A summary model next to it is comfortable with about 16 GB. |
| **Disk** | About 0.6 GB for the smallest transcription model and the speaker model, up to 3 GB more for the most accurate one, plus your recordings. |
| **Summary model** (optional) | [Ollama](https://ollama.com) with at least one model pulled, for recaps, decisions, themes and concepts. Transcription works without it. |

Voxtrama runs on the processor. A graphics card is not needed and is not
used: Docker on macOS cannot reach one, and the transcription library runs
on the processor there as well.

## Start it

```bash
git clone <repository URL> voxtrama
cd voxtrama
cp .env.example .env
make up
```

Nothing in `.env` needs editing before the first start. `make up`:

1. picks a free port on your machine, starting from 8000, unless
   `VOXTRAMA_HOST_PORT` is already set;
2. starts the containers in order: the queue, the database step, then the
   web server and the worker;
3. waits until the web server answers, and prints the address, for
   example `http://127.0.0.1:8000`.

Open that address in your browser. The next page, [First start](first-start.md),
explains what you see there.

!!! note "Without make"
    `docker compose up -d` starts the same containers and always uses
    port 8000. `make up` is a small script around it (`scripts/up.sh`)
    that also waits for the web server and prints the address.

## Where your data goes

Everything Voxtrama keeps lives in one folder on your machine,
`~/Voxtrama` by default: recordings, results, downloaded models, the
database and the settings file. Nothing is kept inside the containers, so
stopping or rebuilding them loses nothing.

To use another folder, set an absolute path in `.env` before starting:

```bash
VOXTRAMA_DATA_DIR=/srv/voxtrama
```

At start-up Voxtrama takes on the owner of that folder, so every file it
writes there is yours to open, copy or delete without `sudo`. See
[Configuration](configuration.md#data-folder) for the layout of the
folder.

## Stop, update, remove

Stop the containers, keeping every file:

```bash
make down
```

Update to a newer version: fetch the new code, then rebuild and start.
The database is brought up to date by the start-up step.

```bash
git pull
docker compose build
make up
```

Remove Voxtrama and everything it kept:

```bash
docker compose down -v
rm -rf ~/Voxtrama
```

These two commands leave nothing behind, because every file Voxtrama
writes is inside that one folder.

## Check the installation

```bash
docker compose exec web voxtrama doctor
```

`doctor` reports the memory, cores and free disk it sees, whether the data
folder can be written, whether the queue answers, which profile suits the
machine, and whether a summary model server is reachable. It suggests
settings and never changes them. It is the first thing to run, and to
paste into a question, when something does not work.
