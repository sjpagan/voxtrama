# Voxtrama

**From audio to verifiable knowledge.**

Voxtrama turns recordings you already have (meetings, lessons, interviews)
into a transcript with the speakers told apart, and then into a recap,
decisions, themes or key concepts. Every point it writes carries a quote
from the recording and the time it was said, so you can play the passage
and check it.

It runs on your own machine, in Docker. The audio never leaves the
installation unless you point a job at a remote model server yourself.

![A finished job: the recap, with each point linked to the moment it was said](images/job-recap.png)

## What it does

- **Transcribes** audio with Whisper, on the processor of your machine.
- **Tells the speakers apart** in one recording, and lets you name them.
- **Runs a workflow** on the transcript: a recap plus decisions, themes or
  concepts, written by a summary model running in
  [Ollama](https://ollama.com).
- **Ties every generated point to the audio.** A point whose quote cannot
  be found in the transcript is marked "Needs review" instead of being
  shown as fact.
- **Keeps a record of each job**: which models ran, with which settings, on
  which file. You can regenerate a job with other choices and keep what
  did not change.
- **Deletes what you no longer need**, by hand or after a retention period
  you choose.

## What it does not do, on purpose

- **It does not remember voices.** Speakers are told apart inside one
  recording, and no voice print is kept to recognise a person in the next
  one. You name speakers by hand.
- **It does not download audio from other sites.** It works on files you
  already have.

## Where to start

<div class="grid cards" markdown>

- **[Install](install.md)**: Docker, one command, and where your data goes.
- **[First start](first-start.md)**: what Voxtrama proposes for your
  machine, and the one download before the first job.
- **[Start a job](new-job.md)**: add audio, pick a workflow, read the
  result.
- **[Troubleshooting](troubleshooting.md)**: what to check when something
  does not work.

</div>

Voxtrama is pre-release software heading for a first alpha. Screens and
settings may still change between versions.
