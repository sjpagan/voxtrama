# Settings pages

**Settings** in the side bar opens what this installation runs with. The
values are saved in `voxtrama.toml` in the data folder, a plain text file
you can also edit by hand.

![Settings](images/settings.png)

## Settings

The first page shows the profile, the parallelism, the summary model and
the address of the model server, and lets you change each one without
going through the whole setup:

- **Change profile**: Efficient (Whisper small), Balanced (Whisper medium)
  or Maximum accuracy (Whisper large-v3).
- **Change parallelism**: cores per chunk and chunks in parallel.
- **Change generative model**: the model the recap and the extractions use,
  among those installed on the model server. **Use at most** caps the
  model's context window, see
  [Summary models and servers](model-servers.md#context-window).
- **Restart setup** runs the guided setup again from the first step, with
  the machine measured again.

A value set in the environment wins over the file, and is marked **from
environment**: saving it here then has no effect.

## Local processing

The three transcription profiles, with the download size of each model,
the room it takes on disk, an estimate of how long an hour of audio takes
on this machine, and its licence. **Download** and **Remove** manage the
models; **Fine-tune** sets the cores and the chunks.

A model you remove is downloaded again the next time a job needs it.

## Model ready

Where Voxtrama finds the summary model. See
[Summary models and servers](model-servers.md).

## Private storage

The data folder, checked with a real write test, and the free space on
its disk.

## Data & privacy

![Data & privacy](images/privacy.png)

- **Where your data lives**: the data folder, and how much room the
  recordings, the jobs, the models and the database take.
- **Model servers**: each configured summary model server, on this
  machine or remote.
- **What each workflow does with the content**: for each step of each
  workflow, whether it runs inside Voxtrama, on a model server on this
  machine, or leaves this machine. A step kept on this machine by
  `local_only` shows that a job sending it to a remote server would be
  refused.
- **Who writes the files**: the user Voxtrama writes as, the owner of the
  data folder, and a write test on each folder. When a test fails, the
  page says why (missing folder, read-only disk, wrong owner, permissions)
  and what to do.
- **Data retention**: how long finished jobs are kept. See
  [Retention](jobs.md#retention).

## Models

The **Models** page (`/models`, also linked from the header chip) lists
what is downloaded and what it costs on disk: the three
transcription models, the speaker model, and the models the summary
server offers.

![Models](images/models.png)

## Your profile

The avatar at the top right opens **Your profile**: your first and last
name, shown on the jobs you create. The name stays on this machine.
