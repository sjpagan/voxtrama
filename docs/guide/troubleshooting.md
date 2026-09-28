# Troubleshooting

Start with `docker compose exec web voxtrama doctor`: it checks the
machine, the data folder, the queue and the model server in one go, and
says what to set. See [Command line](cli.md#doctor).

## The page does not open

- `make up` prints the address when the web server answers. If it waits
  forever, `docker compose logs web` says why.
- Another program may already use port 8000: set `VOXTRAMA_HOST_PORT` in
  `.env` (see [Configuration](configuration.md)).
- Opening Voxtrama through an address other than `127.0.0.1` or
  `localhost` gives **Forbidden: unknown host**. Add that name to
  `VOXTRAMA_ALLOWED_HOSTS`.

## A job stays queued, or the worker is not responding

The worker runs the jobs; the web server only shows them.

```bash
docker compose ps
docker compose logs worker
```

- The worker is not running: `make up` starts it again.
- The worker restarted during a job: that job is marked **Interrupted**,
  and **Retry this step** starts it again from where it stopped.
- The first job of a model waits for the download, which the Activity
  panel shows.

## When a job fails

A failed job keeps what its finished steps produced. The page names the
cause:

| The page says | What to do |
|---|---|
| **No summary model configured** | choose one in **Settings › Change generative model**, then **Retry this step** |
| **No summary model reachable** | start Ollama, or check the address in [Summary models and servers](model-servers.md), then retry |
| **This job ran out of time** | a call to the summary model took longer than its limit: use a smaller or faster model, a server with a graphics card, or raise `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` |
| **This step ran out of memory** | lower the cores per chunk and the chunks in parallel in **Settings › Change parallelism**, or pick a smaller transcription profile |
| **The worker stopped responding** | often the same as running out of memory; the same remedies apply |

Anything else shows the error as the step reported it.

## The upload is refused

| Message | Why |
|---|---|
| **The upload is too large** | over `VOXTRAMA_MAX_UPLOAD_MB` (8 GB by default) |
| **Not enough room in the data folder** | the upload needs about three times its size free |
| **not an audio or video file** | the file is not a container Voxtrama accepts, for example a playlist |

## The transcript has no punctuation or odd words

- Choose the recap language of the audio in the new-job form: it is also
  the language Whisper transcribes in.
- Write a context: the names, products and acronyms that come up. Whisper
  reads it before the audio.
- A larger transcription profile is slower and more accurate.

## The speakers are wrong

Telling speakers apart is experimental, and depends heavily on the quality
of the recording. Name the voices and fix single sentences as the
[Speakers](job-page.md#speakers) section of the job page explains.

## Something else

Paste the output of `voxtrama doctor` and the last lines of
`docker compose logs worker` when you ask for help. They never contain the
model server's credential.
