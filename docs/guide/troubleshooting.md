# Troubleshooting

Start with `docker compose exec web voxtrama doctor`. The command checks the machine, the data folder, the queue and the model server in one pass, and says what to set. [Command line](cli.md) describes its report.

When you ask for help, paste the output of `doctor` and the last lines of `docker compose logs worker`. Neither contains a model server credential.

## The page does not open

| Symptom | Cause | Fix |
|---|---|---|
| `make up` waits and ends with `web did not answer at <address> within 180s` | the web server is still starting, or failed | run `docker compose logs web` |
| `make up` prints `the 'web' container is not running, see: docker compose logs web` | the container stopped | run `docker compose logs web`; the last line says why |
| `docker compose up` fails with a bind error on the port | another program uses port 8000 | set `VOXTRAMA_HOST_PORT` in `.env`; `make up` picks the first free port from 8000 on its own |
| the address works on this machine and not from another | the port is published on `127.0.0.1` only | open Voxtrama on the machine that runs it |
| the browser shows `Forbidden: unknown host.` | you opened Voxtrama through a name that is not allowed; `127.0.0.1`, `localhost` and `::1` are | add the name to `VOXTRAMA_ALLOWED_HOSTS` in `.env`, as a JSON list, and restart |
| the browser shows `Forbidden: cross-site request.` | a form was sent from another site or origin | open Voxtrama directly, at one of its allowed addresses |

The Voxtrama containers stop at start-up with one of these messages in `docker compose logs`.

| Message | Fix |
|---|---|
| `<folder> belongs to root and is not empty. Choose another data folder, or set VOXTRAMA_RUN_AS_UID and VOXTRAMA_RUN_AS_GID.` | choose another data folder, or set the two variables in `.env` |
| `<folder> is not writable. Check the permissions of the host folder it is bind-mounted from.` | make the folder writable by its owner, or set `VOXTRAMA_RUN_AS_UID` and `VOXTRAMA_RUN_AS_GID` |
| `<folder> does not exist inside the container.` | check that `VOXTRAMA_DATA_DIR` is an absolute path to a folder that exists |

## A job cannot start

A job cannot start while the installation is not ready. The new-job form replaces its button with **A job cannot start yet** and lists what is missing, each with a **Set it up** link.

| Entry | What is missing |
|---|---|
| **Local processing** | the configured hardware profile (`VOXTRAMA_HARDWARE_PROFILE` or `hardware_profile` in `voxtrama.toml`) is not one Voxtrama recognises; the reason is printed next to the entry |
| **Models ready** | the transcription model has not been downloaded; **Set it up** opens **Local processing**, where **Download selected model** fetches it |
| **Private storage** | the data folder cannot be written |
| **Database** | the database is older than this version of Voxtrama; run `docker compose build` for every service, then `docker compose up migrate` |

## A job stays queued

The worker runs the jobs, and the web server only shows them.

```bash
docker compose ps
docker compose logs worker
```

- The worker is not running: `make up` starts it again.
- The first job that needs a model waits for the download, which the Activity panel shows.
- The job page shows **Worker not responding** when the worker stops answering. A command-line job prints `Still queued: no worker has picked it up. The run is not lost.` after 30 seconds, and the job stays in the queue.
- The page shows **Connection lost, retrying...** when the browser loses the web server, which is different from the worker stopping.

When the worker restarts during a job, the job is closed as **Interrupted**. At its next start, the worker queues the job again by itself, once, as a new job that reuses the steps already finished. A transcription cut off half way starts over. If the new job is interrupted too, it is left for you, and **Retry this step** runs it again. A job you stopped yourself is never restarted.

## A job fails

A failed job keeps what its finished steps produced. The page shows a banner with a title, a sentence and one or two buttons.

| Banner | Sentence | Cause and fix |
|---|---|---|
| **No summary model configured** | The transcript is done. The recap needs a local summary model: choose one in Settings. | no summary model is chosen; **Open settings**, choose one in **Change generative model**, then **Retry this step**. A job that needs no recap starts with **Transcription only, no summary** |
| **No summary model reachable** | The transcript is done. The recap needs Ollama, which did not answer. | the model server is stopped or at another address; start Ollama or fix the address ([Summary models and servers](model-servers.md)), then **Retry this step** |
| **This job ran out of time** | Every step that finished is saved. Retrying runs only what is left. | the whole job passed the time it was granted, which Voxtrama computes from the length of the audio, the downloads still needed and a margin for the model; **Retry this step** continues from the saved steps |
| **This step ran out of memory** | This step used more memory than this machine could give it. | **Open settings** and lower **Cores per chunk** and **Parallel chunks** in **Change parallelism**, or choose a smaller profile in **Change profile**; the banner lists the values used and the recommended ones |
| **The worker stopped responding** | The process running this step stopped answering before it could finish, often the same thing as running out of memory. | the same remedies as for memory; the cause can also be a restart of the containers |
| **This job failed** | the message the step reported | see the table of raw messages |

**This job ran out of time** concerns the whole job and not one call to the summary model. A single call to the summary model that takes longer than `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` ends in **This job failed** with the message `<address> did not answer within <seconds>s`.

When a step reports its own message, the banner is **This job failed**, and the message is shown under it.

| Message | Cause and fix |
|---|---|
| `<address> did not answer within <seconds>s` | one call to the summary model took longer than `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` (1800 by default); use a smaller or faster model, a server with a graphics card, or raise the variable |
| `<model>: prompt_eval_count N sits at the requested num_ctx of M: the prompt did not fit` | the context limit is too low for a part of the transcript; raise **Use at most**, or choose a model with a larger window |
| `<model>: still hit the output cap after N resumptions` | the model kept writing past its output limit; choose another model |
| `<host> requires credentials we do not have` | the server answered 401 or 403; set `VOXTRAMA_OLLAMA_AUTH` |
| `<host>: credentials are only sent over https to a remote server` | a remote server is configured with `http` and a credential; use `https` |
| `<host> has no model '<model>'` | the model is not installed on that server; pull it in Ollama or choose another |
| `<host> answered <status>: ...` | the server answered with an error; read its message |
| `<step> is local_only, and provider <name> is remote` | the step must stay on this machine; choose a local model server, or another workflow |
| `<skill>@1.0.0 output: ...` | the answer of the model did not fit the skill's fields; **Retry this step**, or use a larger model |

## The upload is refused

| Message | Status | Cause and fix |
|---|---|---|
| **The upload did not say how large it is** | 411 | the request carried no size; send the files from the new-job form |
| **The upload is too large** | 413 | over `VOXTRAMA_MAX_UPLOAD_MB`, 8192 MB by default, counted for the whole request; the detail gives both numbers |
| **Not enough room in the data folder** | 507 | the upload needs about three times its size free; free some space |
| **The file is not a supported audio format** | 415 | the detail names the reason (see the table of details) |
| **This installation cannot take a recording yet** | 503 | the detail lists each missing state as `key: reason`; fix them as in A job cannot start |

The details of **The file is not a supported audio format**:

| Detail | Cause |
|---|---|
| `<file> is not an audio or video file` | the container is not one of the accepted formats, for example a playlist |
| `<file> has no audio stream` | the file has no audio track |
| `ffprobe could not determine the duration of <file>` | the duration cannot be read |
| `ffprobe could not read <file>: ...` | the file is damaged or unreadable |

The accepted containers are WAV, W64, RF64, MP3, FLAC, Ogg, MOV, MP4, M4A, Matroska, WebM, AAC, AIFF, CAF, ASF, AMR, AVI, MPEG, MPEG-TS and WavPack. The limit of 8192 MB is Voxtrama's own, and not the limit of an online transcription service.

## Transcription is slow

Voxtrama transcribes on the processor. The Docker image is CPU only, and Docker on macOS gives containers no access to the graphics card. Transcription speed therefore depends on the processor, on the transcription profile and on how many cores the job uses.

Measured in September 2026 with Voxtrama 0.1.0 on one machine, an Intel Xeon W-2150B with 64 GB of RAM, with the `high` profile (Whisper large-v3, 4 cores per chunk, 2 chunks in parallel): 21 minutes of audio took 7 minutes 30 seconds to transcribe and 2 minutes 38 seconds to separate the speakers. Yours may be faster or slower.

- Choose a smaller profile in **Settings** under **Change profile**: **Efficient** is Whisper small, **Balanced** is Whisper medium.
- Check **Cores per chunk** and **Parallel chunks** in **Change parallelism**. The values are limited by the cores of the machine, and the transcription of a short clip carries a fixed cost for loading the model.
- Check the processor and memory limits of Docker itself. A container cannot use more than Docker gives it.
- The summary model is often the slowest step. A model on a processor writes a few words per second.

## The recap is cut short, or the step fails on a long recording

A summary model with a small context window can fail on a long transcript. Voxtrama splits the transcript into parts of about 12 000 characters, and a context limit that is too low for a part makes the step fail. See Context window in [Summary models and servers](model-servers.md).

## The language is wrong

Voxtrama transcribes in the language chosen as **Recap language** in the new-job form. It also listens to the first 90 seconds of the audio. When the detected language differs from the chosen one with a probability of at least 0.8, the language of the audio wins. With **Same as the audio**, the detected language is used.

- Choose the language of the audio in **Recap language** when detection gets it wrong.
- Write a context in the new-job form: the names, products and acronyms that come up. Whisper reads it before the audio, which also helps punctuation.
- A larger transcription profile is slower and more accurate.

## The speakers are wrong

Speakers are told apart automatically and can be wrong, and the result depends heavily on the quality of the recording. Voxtrama reports at most 4 voices by default, and `VOXTRAMA_MAX_SPEAKERS` changes the ceiling.

In the **Speakers** tab, name each voice once, and use **Add speaker** for someone the detection missed. In the **Explore** tab, give a single turn to someone else.

For scale, a test on 15 synthetic cases (generated voices, not real recordings) found the right number of speakers in 39 of 45 runs, with a median diarization error rate of 0.14. Real recordings with noise, overlapping speech or a telephone line are harder.

## A point shows Needs review

**Needs review** marks a point whose quote Voxtrama could not find in the transcript. It is not an error. Listen to the passage, then correct the point or keep it. A small summary model writes more points of this kind.

## A model download fails

The setup and the **Models** page show **The download failed:** with the reason. Check the free space in the data folder and the network, then choose **Download** again.

## Related pages

- [Command line](cli.md)
- [Summary models and servers](model-servers.md)
- [Configuration](configuration.md)
- [Follow a job](follow-a-job.md)
- [FAQ](faq.md)
