# Follow a job

After **Start job**, the job page opens and follows the job live. You can close it and come back: the job runs in the worker, not in the browser.

## The step chain

The top of the page shows the steps of the workflow as a chain: **Transcribe**, **Identify speakers**, then the steps that write the recap and the extractions, such as **Recap** and **Extract decisions**. Next to the job's state, a counter such as "2 of 4" says how many steps the job has reached out of the total. The counter disappears when the job ends.

Each step is in one of five states:

| State shown | Meaning |
|---|---|
| **Waiting** | the step has not started |
| **In progress** | the step is running |
| Done, worded by what the step left: **Transcript ready**, **Speakers identified**, **Recap ready**, **Decisions ready**, **Themes ready**, **Concepts ready** | the step finished |
| **Failed** | the step failed |
| **Skipped** | the step did not run, for example because a step it depends on was skipped |

A finished step shows how long it took, as "2 min" or "< 1 min". The duration is read when the page loads, so it appears for a step that finished before you opened the page, or after you reload. A step adopted from an earlier job, which ran nothing, says **Reused** instead of a duration.

The job as a whole has a state, shown next to the chain:

| State on the job page | State in the Jobs list |
|---|---|
| Pending | Queued |
| Running | Running |
| Succeeded | Completed |
| Failed | Failed |
| Cancelled | Cancelled |
| Interrupted | Interrupted |

## Activity

The **Activity** panel shows what the worker is doing, line by line: the model loading, how far into the audio the transcription is, each call to the summary model and how long it took. The same lines are written to `runs/<job id>/run.log` in the data folder.

Above the lines, a progress area shows the step that is running:

- a transcription step shows a position in the audio, for example "12:04 / 18:30";
- a step that writes the recap shows how many parts of the transcript the summary model has read, for example "2 of 4 parts read";
- a step with nothing to count shows a moving bar and the elapsed time;
- the area also shows "Elapsed" time and, when it can estimate it, "about N left".

A finished job keeps its **Activity** panel, closed, under the results.

### Stop a job

**Stop job** in the **Activity** panel cancels the job. A job still waiting in the queue is cancelled at once. A running job is stopped, and the page may take a moment to show it as **Cancelled**. A cancelled job can be deleted or regenerated; its finished steps are kept.

### Notices

Two notices can appear next to the job's state.

| Notice | When it appears | What it means |
|---|---|---|
| **Connection lost, retrying...** | the page has received nothing from the server for 10 seconds | the live connection between the page and the server dropped, and the page is reconnecting. The job itself is not affected. |
| **Worker not responding** | the queue has reported the job gone for three checks in a row, 5 seconds apart, and the job has sent no line or progress for 60 seconds | the worker stopped answering. See [Troubleshooting](troubleshooting.md). |

### After a restart of the worker

When the worker restarts during a job, for example after `docker compose down`, a reboot or the machine going to sleep, the job is closed as **Interrupted**. At the next start of the worker, Voxtrama resumes each interrupted job once, by itself, as a new job on the same recording with the same choices. The steps already finished are reused. In the step that was running, windows the summary model had already answered are not asked again. A transcription cut off halfway starts that step over.

Voxtrama resumes a job only once. If the resumed job is interrupted too, nothing restarts it: press **Retry this step**. A job you stopped is **Cancelled**, not **Interrupted**, and is never resumed.

## How long it takes

Transcription is usually the longest step. It depends on the length of the audio, the Whisper model and the cores the job may use. The **Local processing** settings show, for each model, an estimate of how long an hour of audio takes on this machine. The steps that write the recap depend on the summary model, on the length of the transcript and on where the model server runs.

Measured times, as an example:

| Recording | Transcription | Speakers | Recap and extraction | Total |
|---|---|---|---|---|
| 21 min 09 s, Italian, **Lesson companion** | 7 min 30 s | 2 min 38 s | Recap 1 min 47 s, concepts 2 min 46 s | 14 min 41 s |
| 16 min 00 s, **Research interview** | 9 min 11 s | 1 min 19 s | Recap 7 min 04 s, themes 5 min 58 s | 23 min 32 s |
| the 21 min 09 s recording again, regenerated with **Research interview** | reused | reused | themes 2 min 52 s | 2 min 52 s |
| a 16 second clip (18 runs) | 27 to 31 s | 3 to 27 s | 7 to 40 s | 22 to 90 s |

On this machine, transcription took about 0.35 to 0.57 times the length of the audio. The recap part varies a lot with the transcript and the model: for the second recording the recap took four times as long as for the first. The 16 second clip takes about 30 seconds to transcribe because loading the model costs a fixed time. The regenerated job shows how much reuse saves: the transcript and the speakers were not computed again.

Measured in September 2026 with Voxtrama 0.1.0 on one machine, an Intel Xeon W-2150B with 64 GB of RAM, running Voxtrama 0.1.0 in Docker on the CPU only with the `high` profile (Whisper large-v3, 2 chunks in parallel, 4 threads per chunk) and the summary model `qwen3:4b` on the host's Ollama; yours may be faster or slower.

A model running on the processor writes a few words per second; the same model on a graphics card, on another machine, is many times faster. [Summary models and servers](model-servers.md) explains how to choose a model server.

A job also has a time budget: the startup of the models, any model download still to do, and an allowance for the audio's length and the Whisper model, with a safety margin. A job that exceeds it fails with **This job ran out of time**.

## When a job fails

A failed job keeps everything its finished steps produced. The page shows a banner, a section **What this job did produce** (usually the transcript, with **View transcript**), and the **Activity** panel.

| Banner title | Text under it | Buttons |
|---|---|---|
| **No summary model configured** | The transcript is done. The recap needs a local summary model: choose one in Settings. | **Open settings**, **Retry this step** |
| **No summary model reachable** | The transcript is done. The recap needs Ollama, which did not answer. | **Open settings**, **Retry this step** |
| **This job ran out of time** | Every step that finished is saved. Retrying runs only what is left. | **Retry this step** |
| **This step ran out of memory** | This step used more memory than this machine could give it. | **Open settings**, **Retry this step** |
| **The worker stopped responding** | The process running this step stopped answering before it could finish, often the same thing as running out of memory. | **Open settings**, **Retry this step** |
| **This job failed** | the raw error message | **Retry this step** |

**This job ran out of time** means the budget of the whole job ran out, not one call to the summary model. A single call to the summary model that takes longer than its own timeout fails the job with **This job failed** and the message `provider_timeout`.

The memory banners list **Parallel chunks used** and **Cores per chunk used** with the recommended values for the machine, and a line **This machine** when there is a note about it. **Open settings** leads to the settings that fix the cause: **Model ready** for the summary model, **Local processing** for memory.

**Retry this step** starts the job again from the step that failed. The steps that finished are reused, not run again. When the new attempt succeeds, it takes the place of the failed job. The difference between **Retry this step** and **Regenerate job** is explained in [Correct and regenerate](correct-regenerate.md).

[Troubleshooting](troubleshooting.md) lists each failure and what to do about it.

## Related pages

- [Start a job](new-job.md)
- [Read and check the results](results.md)
- [Correct and regenerate](correct-regenerate.md)
- [Jobs, search and clean-up](jobs.md)
- [Troubleshooting](troubleshooting.md)
