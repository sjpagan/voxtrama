# Command line

The `voxtrama` command runs inside the containers, where the database and
the data folder are. Call it through `docker compose exec`:

```bash
docker compose exec web voxtrama <command>
```

A file you pass to it must be inside the data folder, and named by its
path in the container: `~/Voxtrama/meeting.wav` on your machine is
`/data/meeting.wav` there.

## doctor

```bash
docker compose exec web voxtrama doctor
```

Reports the memory, the cores and the free disk; the data folder's owner
and a real write test; whether the queue and the model server answer; and
which hardware profile suits this machine, with the line to put in `.env`.
It suggests and never applies. `--no-measure` skips timing a real
generation on the model server.

It is the first thing to run, and to paste, when something does not work.

## demo

```bash
docker compose exec web voxtrama demo
```

Runs the sample recording shipped with Voxtrama through a workflow, and
follows it to the end. The first run downloads the models it needs.

## run

```bash
cp meeting.wav ~/Voxtrama/
docker compose exec web voxtrama run transcribe-only /data/meeting.wav
```

Imports the file, starts a job with the named workflow, and follows it to
the end. The job appears in the Jobs page like any other.

| Option | What it does |
|---|---|
| `--detach` | print the job id and return at once |
| `--reuse-from <job id>` | reuse the steps of that job whose inputs did not change |

## compare

```bash
docker compose exec web voxtrama compare /data/runs/<job a> /data/runs/<job b>
```

Compares the manifests of two jobs and reports the differences that count:
another model, other settings, another input file. Ids and times, which
change on every run, are left out. `--show-expected` lists them too.

The exit code is `0` when nothing counts, `1` when at least one
difference does, `2` when a manifest cannot be read.

## retention

```bash
docker compose exec web voxtrama retention
```

Lists the jobs [retention](jobs.md#retention) emptied, and shows that
nothing of them is left on disk.

## correct

```bash
docker compose exec web voxtrama correct <recording id> --label "Weekly sync, 26 September"
```

Corrects the title (`--label`) or the source address (`--url`) recorded
for a recording. Jobs started afterwards see the correction; the records
of jobs already run keep what they ran with.

## version

```bash
docker compose exec web voxtrama version
```
