# Follow a job

After **Start job** the job page opens and follows the job live. You can
close it and come back: the job runs in the worker, not in the browser.

## While it runs

The top of the page shows the steps of the workflow as a chain:
Transcribe, Diarize (telling the speakers apart), then the generative
steps such as Summarize and Extract Decisions. The step running now is
marked, and each finished step shows how long it took.

Below the chain, the **Activity** panel shows what the worker is doing,
line by line: the model loading, how far into the audio the transcription
is, each call to the summary model and how long it took. The same lines
are written to `runs/<job id>/run.log` in the data folder.

**Stop job** in the Activity panel cancels the job. A job still waiting in
the queue is cancelled at once. A running one is stopped, and the page
may take a moment to show it as **Cancelled**.

Two notices can appear next to the job's state:

- **Connection lost, retrying...**: the page lost its live connection to the
  server and is reconnecting. The job itself is not affected.
- **Worker not responding**: the worker has stopped answering. See
  [Troubleshooting](troubleshooting.md#a-job-stays-queued-or-the-worker-is-not-responding).

## How long it takes

Transcription is usually the longest step. It depends on the length of the
audio, the transcription model, and the cores the job may use. The
Local processing settings show, for each model, an estimate of how long
an hour of audio takes on this machine.

The generative steps depend on the summary model and on where it runs. A
model running on the processor writes a few words per second; the same
model on a graphics card, on another machine, is many times faster. See
[Summary models and servers](model-servers.md).

## When a job fails

A failed job keeps everything its finished steps produced. The page shows
what went wrong, what the job did produce (usually the transcript), and
two actions:

- **Retry this step** starts the job again from the step that failed. The
  steps that finished are reused, not run again. When the new attempt
  succeeds, it takes the place of the failed job.
- **Open settings** appears when the cause is a setting, for example a
  summary model that is not configured or not reachable.

[Troubleshooting](troubleshooting.md#when-a-job-fails) lists each failure
and what to do about it.
