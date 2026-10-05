# Update, back up, remove

Updating Voxtrama means fetching the new code, rebuilding the image and running `make up` again; stopping and removing it never touches your recordings unless you delete the data folder yourself.

## Stop Voxtrama

Stopping removes the containers and keeps every file in the data folder.

1. Run, from the folder where you cloned Voxtrama:

    ```bash
    make down
    ```

    You should see the containers `redis`, `web`, `worker` and the network removed. `make down` runs `docker compose down`, so the two are the same.

2. Start again with `make up`.

## Update

Updating needs the new code and a rebuilt image. Do it when no job is running.

1. Fetch the new code:

    ```bash
    git pull
    ```

    You should see the updated files, or `Already up to date.`

2. Rebuild the image:

    ```bash
    docker compose build
    ```

    You should see the build finish without an error.

3. Start Voxtrama:

    ```bash
    make up
    ```

    You should see the four stages of `make up`, ending with the address.

The database is brought up to date by the one-off `migrate` container, which runs `alembic upgrade head` on every start, before the web server and the worker start. Migrations only go forward when Voxtrama starts. Restoring a backup into an older version than the one that wrote it is not supported: see [Taking your data with you](data-portability.md).

If a job was running when the worker restarted, the worker resumes it once on its own. If that second attempt fails too, the job shows the failure and **Retry this step** is offered.

Your `.env` and the data folder are not touched by an update. A new version can add variables to `.env.example`; compare it with your `.env` if a release note says so.

## Back up

A backup is a copy of the recordings, the results, the database, the custom workflows and `voxtrama.toml`. The downloaded models are left out, because they download again on first use. [Taking your data with you](data-portability.md) has the table of what to copy and the commands, for a backup and for a move to another machine.

Stop Voxtrama before copying: a database copied while a job is writing to it can be restored in a state no job ever produced.

## Remove

Removing Voxtrama takes three actions: the containers and the image, the data folder, and the cloned code. Each is separate, so you can stop after the first.

1. Remove the containers and the image:

    ```bash
    docker compose down --rmi all
    ```

    You should see the containers removed, then the images. `--rmi all` removes every image the services use: the ones built from this repository and the `redis` image. A plain `down` leaves the images on disk. Voxtrama defines no named Docker volume: its data is in your own data folder, not in a Docker volume.

2. Delete the data folder, only if you no longer need the recordings and results. This deletes your audio, transcripts and models for good:

    ```bash
    rm -rf ~/Voxtrama
    ```

    Use the path of your own data folder if you set `VOXTRAMA_DATA_DIR`. Back up first if in doubt.

3. Delete the cloned repository folder.

Docker caches built layers separately from images. To reclaim that space too, use Docker's own commands, for example `docker builder prune`. The [Docker documentation](https://docs.docker.com/reference/cli/docker/builder/prune/) describes it.

## Related pages

- [Taking your data with you](data-portability.md)
- [Check the installation](check-installation.md)
- [Configuration](configuration.md)
- [Troubleshooting](troubleshooting.md)
