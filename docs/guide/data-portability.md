# Taking your data with you

Voxtrama keeps everything in one folder on your own disk, and copying that folder moves an installation to another machine. This page says what to copy, what to leave behind, and what the project does not promise about restoring a copy.

## What lives in the data folder

```
$VOXTRAMA_DATA_DIR/            # default: ~/Voxtrama
├── recordings/<id>/           # the audio you imported, and the copies made from it
├── runs/<job id>/             # one folder per job: manifest.json, output.json, run.log
├── models/                    # downloaded model weights
├── logs/                      # created at start-up
├── workflows/                 # your custom workflows, created with the first one
├── voxtrama.toml              # the installation's settings
├── proposal.toml              # the proposal for this machine, until voxtrama.toml exists
└── voxtrama.db                # the database
```

## What to copy

| Item | Copy it? | Why |
|---|---|---|
| `recordings/` | yes | your audio, which nothing can recreate |
| `runs/` | yes | the results, and the evidence behind every field |
| `voxtrama.db` | yes | the database ties each job to its recording; without it, `recordings/` and `runs/` are orphans |
| `workflows/` | yes, if it exists | your custom workflows |
| `voxtrama.toml` | yes | the installation's settings; leave it behind to go through the first start again |
| `proposal.toml` | no | the new machine makes its own proposal |
| `logs/` | no | created again at start-up |
| `models/` | no | the weights are downloaded again on first use, and they make up most of the size |

The download size of each model is shown in **Settings** under **Local processing**.

## Move to another machine

1. Stop Voxtrama, so that no job writes to the database during the copy:

    ```bash
    docker compose down
    ```

2. Create the archive. Add `workflows` to the list only if the `workflows/` folder exists:

    ```bash
    tar -czf voxtrama-backup.tar.gz \
        -C ~/Voxtrama recordings runs voxtrama.db voxtrama.toml
    ```

3. On the new machine, with Voxtrama installed and not running, unpack the archive into the data folder:

    ```bash
    mkdir -p ~/Voxtrama
    tar -xzf voxtrama-backup.tar.gz -C ~/Voxtrama
    ```

4. Start Voxtrama:

    ```bash
    make up
    ```

You should see: the jobs and recordings of the old machine in the Jobs page. The first job that needs a model downloads it again.

If the data folder lives somewhere other than `~/Voxtrama`, set `VOXTRAMA_DATA_DIR` in `.env` before you start. The data folder must not be owned by root and non-empty. When it is, the container stops and the log says `<folder> belongs to root and is not empty. Choose another data folder, or set VOXTRAMA_RUN_AS_UID and VOXTRAMA_RUN_AS_GID.` Choose another folder, or set the two variables.

A folder that arrives owned by another user id needs no `sudo`. At start-up, the container aligns the `voxtrama` user with the owner of the data folder.

## Update and restore

On every start, the `migrate` service brings the database to the version of the installed Voxtrama. It only upgrades. The migration files contain a downgrade step, and nothing in Voxtrama runs it.

- A backup restores into the same version it was taken from, or into a newer one.
- A backup does not restore into an older version of Voxtrama, because a newer version may have migrated the database.
- When the database is older than the code, the upload form refuses a recording with `This installation cannot take a recording yet`, and the detail says to run `docker compose build` and then `docker compose up migrate`.

## Workflow files in a backup

Workflow files carry a `schema_version`. This version of Voxtrama reads `v1` and refuses any other value. Before version 1.0 there is no compatibility promise: a release may change the shape, and its release notes say how to adapt your files. Your jobs stay readable. Running an old workflow definition again is a separate matter, and it can fail with `Input should be 'v1'`.

## The backup file

The archive is a plain, unencrypted copy of your recordings and transcripts, wherever you keep it. The audio is often sensitive, so the archive deserves the same care as the recordings it holds. [Privacy and data](privacy.md) lists what the folder contains.

## No backup command

There is no `voxtrama backup` command, because `tar` already does the work on every platform Voxtrama runs on. [Update, back up, remove](update-remove.md) covers the whole life of an installation.

## Related pages

- [Update, back up, remove](update-remove.md)
- [Configuration](configuration.md)
- [Privacy and data](privacy.md)
- [Workflow files](workflow-files.md)
