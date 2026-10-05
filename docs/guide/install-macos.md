# Install on macOS

Installing Voxtrama on macOS takes Docker Desktop, a copy of the repository and one command, `make up`. Voxtrama 0.1 has been tested end to end on macOS with an Intel processor; Apple Silicon has not been tested end to end yet.

## Before you start

Check the [Requirements](requirements.md) first: memory, disk and the tools `make up` needs on the host.

1. Open Terminal and run:

    ```bash
    make --version
    python3 --version
    curl --version
    git --version
    ```

    You should see a version line for each command. If macOS offers to install the command line developer tools, accept: they provide `make`, `python3` and `git`.

## Install Docker Desktop

Voxtrama runs in Docker containers, and on macOS Docker Desktop provides them.

1. Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/).
2. Start Docker Desktop and wait until it reports that Docker is running.
3. Run:

    ```bash
    docker compose version
    ```

    You should see a Docker Compose version line.

### Why Docker on macOS does not use the GPU

Docker Desktop runs containers inside a Linux virtual machine, and that virtual machine cannot reach the graphics chip of the Mac. Voxtrama therefore transcribes on the processor, whatever Mac you have, and its image is built for the processor only. A summary model is different: Ollama runs on the host, outside Docker, and can use the graphics chip of an Apple Silicon Mac. See [Set up the summary model](summary-model-setup.md).

### Memory and cores given to Docker Desktop

Docker Desktop gives the virtual machine a fixed share of the Mac's memory and cores, and Voxtrama sees only that share. Voxtrama reads the memory and cores visible inside the container, so `voxtrama doctor` and the guided setup propose a profile for the Docker Desktop allocation, not for the whole Mac.

1. In Docker Desktop, open **Settings**, then **Resources**.
2. Raise **Memory** to what the profile you want needs: about 8 GB or less for Low, between 8 GB and 32 GB for Base, 32 GB or more for High. See [Requirements](requirements.md).
3. Raise **CPUs** to the number of cores you want Voxtrama to use.
4. Press **Apply & restart**.

    You should see Docker Desktop restart. Restart Voxtrama afterwards with `make down` and `make up`.

The labels and defaults of the Resources page change between Docker Desktop versions: see the [Docker Desktop documentation](https://docs.docker.com/desktop/) for the current ones.

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

    You should see four stages: `=== 1. host port ===`, `=== 2. docker compose up ===`, `=== 3. waiting for web to answer ===` and `=== 4. ready ===`, followed by an address such as `http://127.0.0.1:8000`. The first run builds the image, so it takes longer than the next ones.

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
VOXTRAMA_DATA_DIR=/Users/yourname/voxtrama-data
```

At start-up, Voxtrama takes on the owner of the data folder, so every file it writes there is yours to open, copy or delete without `sudo`. If the folder does not exist yet, Docker creates it, and Voxtrama then claims it. If the folder belongs to root and already contains files, the container refuses to start with a message that says the folder "belongs to root and is not empty": choose another folder, or set `VOXTRAMA_RUN_AS_UID` and `VOXTRAMA_RUN_AS_GID`. See [Configuration](configuration.md) for the layout of the folder.

On Docker Desktop, the folder you choose must be one Docker Desktop is allowed to share. Docker Desktop's file sharing settings decide which folders those are: see the [Docker Desktop documentation](https://docs.docker.com/desktop/) if Docker reports that the folder cannot be mounted.

## Next

Voxtrama works for transcription as it is. Recaps need a summary model: see [Set up the summary model](summary-model-setup.md).

## Related pages

- [Requirements](requirements.md)
- [Set up the summary model](summary-model-setup.md)
- [First start](first-start.md)
- [Check the installation](check-installation.md)
- [Troubleshooting](troubleshooting.md)
