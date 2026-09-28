# Taking your data with you

Voxtrama keeps everything on your own disk, in one folder you can open.
This page says what to copy when you
move to another machine, what you can safely leave behind, and what the
project does *not* promise about restoring it.

## What lives in the data directory

```
$VOXTRAMA_DATA_DIR/            # default: ~/Voxtrama
├── recordings/                # the audio you imported
├── runs/<run_id>/             # one folder per job: manifest, output, log
├── models/                    # downloaded model weights
├── workflows/                 # your custom workflows
├── voxtrama.toml              # the installation's settings
└── voxtrama.db                # the state
```

## What to copy, and what not to

| | Copy it? | Why |
|---|---|---|
| `recordings/` | **yes** | your audio. Nothing can recreate it |
| `runs/` | **yes** | the results, and the evidence behind every field |
| `voxtrama.db` | **yes** | without it, the files above are orphans: the database is what ties a run to its recording |
| `workflows/` | **yes** | your custom workflows, if you made any |
| `voxtrama.toml` | **yes** | the installation's settings; leave it behind to go through the first start again |
| `models/` | no | weights re-download on first use. This is the bulk of the size |

Leaving `models/` behind is what turns a multi-gigabyte copy into a few
hundred megabytes.

## Moving to another machine

Stop Voxtrama first. A database copied while a run is writing to it can be
restored in a state no run ever produced.

```bash
docker compose down
tar -czf voxtrama-backup.tar.gz \
    -C ~/Voxtrama recordings runs workflows voxtrama.db voxtrama.toml
```

Leave `workflows` out of the list if you never made a custom workflow:
`tar` stops on a folder that does not exist.

On the new machine, with Voxtrama installed but not running:

```bash
mkdir -p ~/Voxtrama
tar -xzf voxtrama-backup.tar.gz -C ~/Voxtrama
docker compose up
```

The first run will re-download the models it needs. Set `VOXTRAMA_DATA_DIR` in
`.env` if the folder lives somewhere other than `~/Voxtrama`.

File ownership is realigned at startup,
so a folder that arrives owned by a different user id does not need `sudo` to
be usable.

## What is not promised

**Restoring into an older version of Voxtrama.** A newer version may have
migrated the database, and those migrations do not run backwards. Restore into
the same version you backed up from, or a newer one.

**That a workflow file from an old backup still runs.** Workflows carry a
`schema_version`, and which ones a given release accepts is a decision that
has not been made yet. Your runs stay readable; re-running an old workflow
definition is a different promise.

**Anything about the backup file itself.** It is a plain archive of your own
recordings and transcripts, unencrypted, wherever you choose to keep it. The
audio is usually sensitive: that is the reason Voxtrama exists at all, and the
archive deserves the same care as the recordings it holds.

## Why there is no `voxtrama backup` command

`tar` already does this, on every platform Voxtrama runs on, and a command
that wraps it is one more thing to keep working across three operating
systems. If the procedure above turns out to be awkward in practice, that is
the moment to add one.
