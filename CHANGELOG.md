# Changelog

## 0.1.0-alpha2

Four corrections on top of the first alpha, all found by running it on
real recordings.

### Fixed

- Transcription decoded on a fraction of the cores it was given. The two
  numbers the settings show, cores per chunk and parallel chunks, reached
  Whisper as a thread count and a worker count. Nothing splits a recording
  into chunks, so the second worker was allocated and never ran, while the
  cores it had claimed stayed idle. On a machine reporting twenty
  processors, a job set to four cores and two chunks decoded on four
  threads. The whole declared budget now goes to the single call that
  exists.
- Saving a summary model erased the context ceiling measured for every
  other one. Picking one of those again fell back to a small default,
  silently, which is enough to truncate a transcript of forty minutes.
  Every measured ceiling is kept now, and each form on the settings page
  carries the ceiling of the model it names.
- A request that failed while the browser was on a page answered with a
  JSON document, so a person read a machine format instead of a message.
  A request that asks for a page now gets one, with the same message and
  the same status. A client that asks for JSON still receives exactly what
  it received before.
- Times were shown in the timezone of the machine running Voxtrama rather
  than of the person reading the screen. Two hours out in western Europe
  in summer, and a job started after midnight appeared under the day
  before. The log on disk stays in UTC, which is what makes two machines
  comparable, and the page converts it.

## 0.1.0-alpha1 (first alpha)

The first version meant to be installed by someone other than its author.
The whole path works on one machine: audio in, a transcript with its
speakers, and a recap whose every point links back to the moment it was
said. It is an alpha: nothing here is a compatibility promise, and
the measurements that stop a release from getting worse are not in place
yet. Released under the Apache License 2.0.

### What it does

- Transcribes audio with Whisper on the processor, after cleaning it up:
  a high-pass filter, noise reduction and even loudness.
- Tells the speakers apart in one recording. The **Speakers** tab names
  each voice, counts its turns, plays its first minute, and adds speakers
  diarisation missed. A single turn can be given to someone else in
  Explore.
- Runs four workflows (transcript only, meeting decisions, lesson
  companion, research interview) with a summary model served by Ollama,
  on this machine or on a remote server with a credential.
- Ties every generated point to a quote and a time. A point whose quote is
  not in the transcript is marked **Needs review**. A person can rewrite
  it or tie it to another turn, and it then shows as **Edited**.
- Reads a long transcript in parts of about 12,000 characters, two at a
  time by default. An answer the model already gave is kept, so a retry
  asks only for the parts still missing.
- A job cut off by a restart starts again by itself once, reusing the
  steps it had finished.
- Follows a job live, stops it while it runs, regenerates it with
  other choices, and deletes it, keeping audio another job still uses.
  Retention deletes finished jobs after a chosen number of days.
- The **Files** tab of a finished job gives the transcript as text,
  Markdown, JSON or JSONL, the recap, the manifest, and one ZIP with the
  recording cut into parts of about ten minutes, each next to its text.

### Security

- HTML escaped in every template, Host and Origin checked on every
  request, security headers on every response.
- Credentials go to a model server only over `https` or on this machine,
  redirects are not followed, and an address carrying a password is
  refused. Uploads have a size limit.
- Only known audio formats are accepted. The speaker model is pinned to a
  revision.

### For whoever installs it

- Dependencies pinned in lock files.
- A user guide built with MkDocs, under `docs/guide/`, and a README
  that starts from installation.
- `scripts/first-run-check.sh` runs the whole path from an empty folder,
  and stops the stack whatever happens.
