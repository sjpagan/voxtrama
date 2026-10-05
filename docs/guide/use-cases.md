# Use cases

Voxtrama fits three kinds of recording out of the box: meetings, research interviews and lessons. Each has a workflow, a few settings worth changing and a check to make before you rely on the result. Everything on this page holds for Voxtrama 0.1 as it is shipped.

## Meeting minutes

Use the **Meeting decisions** workflow. It produces key points, and the decisions with their owner and deadline, each with a quote from the recording.

### Settings

| Setting | Value | Why |
|---|---|---|
| **Workflow** | **Meeting decisions** | adds the **Decisions** section to the recap |
| **Context** | names of the people, acronyms, project names | Whisper spells them right, and the summary model can match an owner to a name; see [Start a job](new-job.md) |
| **Summary detail** | 3 (default), 2 for a short stand-up | about 8 points for a meeting, 5 for a short one |
| **Recap language** | the language the minutes are to be written in | it is also the language the audio is transcribed in, unless the first 90 seconds are clearly in another language |
| **At the same time** | when each person was recorded on their own microphone | the tracks are mixed into one before the speakers are told apart |
| `VOXTRAMA_MAX_SPEAKERS` | raise it to more than 4 for a larger meeting | the default ceiling is 4 speakers; see [Speakers](speakers.md) |

### What to check

1. In the **Recap** tab, press the time of each decision and listen to the quote. The owner and the deadline of a decision are the model's reading of that passage; confirm them against the audio.
2. Treat every point marked **Needs review** as unconfirmed until you find the passage; [Read and check the results](results.md) shows how.
3. Name the voices in the **Speakers** tab before you export, so that the minutes carry names and not `spk0`.
4. Export the minutes as **DOCX** or **PDF** from **Export**; the file keeps each point's speaker, its time and any **Needs review** mark.

## Research interviews

Use the **Research interview** workflow. It produces key points, and the themes with the insight behind each, each with a quote.

### Settings

| Setting | Value | Why |
|---|---|---|
| **Workflow** | **Research interview** | adds the **Themes** section |
| **Context** | the topic of the study, the names that recur, the technical terms | spelling of terms in the transcript |
| **Summary detail** | 4 for an interview with many topics | about 12 points, a short paragraph each |
| **Model server** | a model server on this machine | the context and the transcript reach the summary model only on the server you chose; the new-job form marks each server local or remote |
| **Delete after** | the period your protocol allows, 7, 30, 90 or 365 days | audio, transcript and recap are deleted then, and only an emptied record stays |
| `privacy: local_only` | on the generative steps, in a custom workflow | a job that would send them to a remote server is refused; see [Workflows and skills](workflows.md) |

Voxtrama does not keep a voice print: speakers are told apart inside one recording and named by hand, so no biometric profile of a participant stays in the installation. See [Privacy and data](privacy.md).

### What to check

1. For each theme, press the time of its quote and listen: a theme is only as good as the passage it points to.
2. Correct the wording of a point, or tie it to the right turn, with **Edit or link to another turn**; the model's own text stays in the job's record.
3. Name the speakers, and give a sentence to the right person in **Explore** when the voices were merged.
4. Export the transcript as **JSON** or **JSONL** to code it in another tool, and keep `manifest.json` with the study: it records the models and the settings of each job.

## Lessons

Use the **Lesson companion** workflow. It produces key points, and the key concepts with their definitions, each with a quote.

### Settings

| Setting | Value | Why |
|---|---|---|
| **Workflow** | **Lesson companion** | adds the **Concepts** section |
| **Summary detail** | 4 or 5 for study notes | level 5 asks for one point per minute of recording, from 15 to 40, each a paragraph with a quote |
| **Recap language** | the language you study in | it is also the language the audio is transcribed in, unless the first 90 seconds are clearly in another language; **Same as the audio** follows the lesson |
| **One after another** | when the lesson was recorded in several files | the files are joined in the order shown into one transcript |
| **Context** | the subject, the names of the authors and the technical terms | spelling of terms in the transcript |

A long lecture is read by the summary model in windows of about 12,000 characters. The model's context must be large enough for one window; [Summary models and servers](model-servers.md) explains the limit.

### What to check

1. Press the time of a concept and listen to the explanation it comes from; confirm that the definition says what the teacher said.
2. Treat a concept marked **Needs review** as unconfirmed.
3. Use **Search transcript** in the **Transcript** tab to find the passage on a topic and play it.
4. Export the recap as **PDF** to print, or the transcript as **Markdown** to keep with your notes.

## Related pages

- [Your first job](first-job.md)
- [Workflows and skills](workflows.md)
- [Read and check the results](results.md)
- [Privacy and data](privacy.md)
