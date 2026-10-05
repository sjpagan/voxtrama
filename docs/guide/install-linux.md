# Install on Linux

Installing Voxtrama on Linux takes Docker Engine with the Compose plugin, a copy of the repository and one command, `make up`. Linux has not been tested end to end yet for Voxtrama 0.1: the steps here follow the project files, and any difference you find is worth reporting.

## Before you start

Check the [Requirements](requirements.md) first: memory, disk and the tools `make up` needs on the host.

1. Open a terminal and run:

    ```bash
    make --version
    python3 --version
    curl --version
    git --version
    docker compose version
    ```

    You should see a version line for each command. Install what is missing with your distribution's package manager.

2. Check that your user can run Docker without `sudo`:

    ```bash
    docker ps
    ```

    You should see a table header (`CONTAINER ID`, `IMAGE` and so on), possibly with no rows. If you see a permission error, add your user to the `docker` group as Docker's documentation describes, and log in again. Installing Docker Engine depends on your distribution: follow the [Docker Engine installation guide](https://docs.docker.com/engine/install/).

## Get Voxtrama

1. Clone the repository:

    ```bash
    git clone https://github.com/sjpagan/voxtrama.git voxtrama
    cd voxtrama
    ```

2. Copy the example settings file:

    ```bash
    cp .env.example .env
    ```

    Nothing in `.env` needs editing before the first start. The variables you may want later are in [Configuration](configuration.md).

## Start Voxtrama

1. Run:

    ```bash
    make up
    ```

    You should see four stages: `=== 1. host port ===`, `=== 2. docker compose up ===`, `=== 3. waiting for web to answer ===` and `=== 4. ready ===`, followed by an address such as `http://127.0.0.1:8000`.

2. Open that address in your browser.

    You should see the guided setup, on the **Local processing** step. See [First start](first-start.md).

### What `make up` does

`make up` runs `scripts/up.sh`, which:

1. uses the port in `VOXTRAMA_HOST_PORT` if it is set in the shell or in `.env`, and otherwise takes the first free port starting from 8000;
2. runs `docker compose up -d`, which starts the queue, then the database step, then the web server and the worker;
3. polls `http://127.0.0.1:<port>/health` every 2 seconds, for up to 180 seconds, and stops with a message if the `web` container is not running or does not answer in time;
4. prints the address and how to follow the logs (`docker compose logs -f`) and stop Voxtrama (`make down`).

Voxtrama publishes its port on `127.0.0.1` only, so no other machine can reach it. The web server answers only to the host names `127.0.0.1`, `localhost` and `::1`. To open Voxtrama through another name, for example behind your own proxy, add it to `VOXTRAMA_ALLOWED_HOSTS` in `.env`; see [Configuration](configuration.md).

### Without make

`docker compose up -d` starts the same containers. It publishes `VOXTRAMA_HOST_PORT` if it is set in `.env`, and port 8000 otherwise. It does not look for a free port and does not wait for the web server: if port 8000 is taken, it fails with a port error.

```bash
docker compose up -d
```

## Where your data goes

Voxtrama keeps everything in one data folder, `~/Voxtrama` by default: recordings, results, downloaded models, the database and the settings file. Nothing is kept inside the containers, so stopping or rebuilding them loses nothing.

To use another folder, set an absolute path in `.env` before the first start. Compose does not expand `~`.

```bash
VOXTRAMA_DATA_DIR=/srv/voxtrama
```

At start-up, Voxtrama takes on the owner of the data folder, so every file it writes there is yours to open, copy or delete without `sudo`.

- If the folder does not exist yet, Docker creates it owned by root on the first run. Voxtrama then claims it, because it is empty.
- If the folder belongs to root and already contains files, the container refuses to start with a message that says the folder "belongs to root and is not empty". Choose another folder, or set `VOXTRAMA_RUN_AS_UID` and `VOXTRAMA_RUN_AS_GID` in `.env` to the numeric user and group that should own the files.
- On a network mount, or when a service account must own the files, set `VOXTRAMA_RUN_AS_UID` and `VOXTRAMA_RUN_AS_GID` as well: the owner Voxtrama detects may not be the effective one.

See [Configuration](configuration.md) for the layout of the folder.

## Reaching Ollama from the containers

The project file maps the name `host.docker.internal` to the host for the web server and the worker, so Voxtrama can reach an Ollama running on the same machine at `host.docker.internal:11434`. Ollama must accept connections coming from the Docker network: see [Set up the summary model](summary-model-setup.md).

## Related pages

- [Requirements](requirements.md)
- [Set up the summary model](summary-model-setup.md)
- [First start](first-start.md)
- [Check the installation](check-installation.md)
- [Troubleshooting](troubleshooting.md)
