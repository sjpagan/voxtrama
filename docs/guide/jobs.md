# Jobs, search and clean-up

## The Jobs page

**Jobs** in the side bar lists every job: its name, workflow, audio
length, date and status. A running job shows how many of its steps are
done. The **⋮** menu on each row opens the job, regenerates it (finished
jobs only) or deletes it.

![The Jobs page](images/jobs.png)

| Status | Meaning |
|---|---|
| Queued | waiting for the worker |
| Running | a step is running |
| Completed | every step finished |
| Failed | a step failed; what finished before it is kept |
| Cancelled | stopped on request |
| Interrupted | the worker stopped during the job |

## Search

The search field at the top of every page looks through the text of every
transcript and every job name. Type at least two characters. Results are
grouped by job and show the time, the speaker and the sentence; click one
to open the job at that sentence.

![Search results](images/search.png)

Search does not look into recaps, extractions or settings.

## Delete a job

**Delete...** in a job's menu asks what to delete:

- **Recap**: the recap and the extractions. The transcript and the audio
  stay, and the job can be regenerated from them.
- **Transcript**: this job's transcript.
- **Audio**: the recording's files.

Anything left unchecked stays. Ticking all three removes the job itself.

Each job behaves as if its audio were its own. A regenerated job uses the
same recording as the job it came from; deleting either one, or only its
audio, never touches the other:

- deleting the whole job keeps the recording for the other job;
- deleting only the audio takes the player away from this job, and the
  other job keeps the audio;
- the files are removed with the last job that uses them.

While a job regenerated from this one is still running, this job cannot be
deleted: wait for it to finish.

Only finished jobs can be deleted. A running job can be stopped first
from its page.

## Clean up

**Clean up** on the Jobs page removes:

- failed, cancelled and interrupted jobs that ended a week ago or more;
- recordings that no job uses, imported a week ago or more;
- folders in the data folder that belong to no job.

The worker also cleans up this way when it starts and once a day. A job
that another job was started from is kept while that job runs.

## Retention

Retention deletes finished jobs after a number of days. Set it in
**Settings › Data & privacy** under **Data retention**: never (the
default), 7, 30, 90 or 365 days.

- A job past its limit loses its audio, transcript, recap and files.
  Only an emptied record stays, saying the job existed and was deleted.
- The limit that applies is the shortest of three: the installation's, the
  workflow's, and the job's own (**Delete after** in the new-job form).
  A job can ask to be kept for less time, never for more.
- A recording that another job still uses is kept.
- Retention runs when the worker starts, once a day, and on **Clean up**.
  It does not run the moment you save the setting.

The job page shows when a job will be deleted, for example "Deleted on
Dec 26, 2026". To check what retention removed:

```bash
docker compose exec web voxtrama retention
```
