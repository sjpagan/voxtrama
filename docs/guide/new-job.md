# Start a job

A job is one recording, one workflow and the choices it runs with. You
start it from the home page.

![The new-job form with two files added](images/new-job.png)

## Add the audio

Drop audio files on the **Audio** card, or press **Choose files**. Any
audio file your browser recognises can be added: WAV, FLAC, MP3, M4A,
OGG and so on. Voxtrama checks each one when the job starts and refuses a
file that has no audio track or whose length cannot be read.

The original file is stored untouched in the data folder. Voxtrama works
on a 16 kHz mono copy it makes next to it.

### Several files in one job

When you add two or more files, the list shows each part with its length,
and asks how they relate:

- **One after another**: the parts continue from each other, like
  segments of one long recording. They are joined in the order shown.
- **At the same time**: separate microphones or channels recorded
  together. They are mixed into one track, aligned at the start, and the
  speakers are told apart from the mix.

Drag a part by its grip to change the order, or remove it with its
cross. The job is made of the parts exactly as the list shows them.

## Pick a workflow

The workflow decides what the job produces besides the transcript:

| Workflow | Produces |
|---|---|
| **Meeting decisions** | a recap, and the decisions with their owner and deadline |
| **Lesson companion** | a recap, and the key concepts with their definitions |
| **Research interview** | a recap, and the themes with the insight behind each one |

Every workflow transcribes the audio and tells the speakers apart first.
To get the transcript alone, tick **Transcription only, no summary** under
**Advanced**. [Workflows and skills](workflows.md) explains each step,
and how to build your own workflow.

## Name and context

- **Job name**: filled in from the first file's name until you type your
  own. Up to 200 characters.
- **Context**: a few words about the recording, up to 2,000 characters.
  Names, acronyms and topics help most: "Weekly product sync. People:
  Alex, Taylor. Topics: mobile roadmap, API migration."

The context is read by the transcription model, which then spells those
names right, and by the summary model. The transcription model only reads
the first 600 characters. The summary model is told that where the
context and the transcript disagree, the transcript wins.

When you leave the context empty, Voxtrama deduces one from the
transcript before the recap and shows it on the job page as
**Context deduced**.

!!! warning "Context and remote servers"
    The context is kept in the job's record. If the job runs on a remote
    summary model server, the context is sent there along with the
    transcript.

## Advanced options

**Advanced** opens the choices this one job can make. Each field starts
from the installation's setting and shows **Default**. A field you move
shows **Changed**, and only changed fields become the job's own choices.

![The Advanced options](images/new-job-advanced.png)

| Option | What it does |
|---|---|
| **Transcription model** | Whisper small, medium or large-v3. Larger is more accurate and slower. A model not downloaded yet is downloaded by the job before it starts transcribing. |
| **Parallel chunks** | How many pieces of the recording are transcribed at the same time. |
| **Cores per chunk** | How many processor cores each piece uses. The hint shows the total against the cores the machine has. A job that asks for more cores than the machine has is refused. |
| **Summary model** | Which model of the summary server writes the recap and the extractions. |
| **Summary detail** | From 1 to 5, how long the recap is (see below). |
| **Recap language** | The language the recap and extractions are written in, and the language the audio is transcribed in. It starts from your browser's language. If the first minute and a half of speech is clearly in another language, the audio's language is used for the transcript. **Same as the audio** follows the language detected in the recording. |
| **Model server** | Shown only when more than one summary server is configured. Each is marked local or remote. |
| **Delete after** | Retention for this job: its audio, transcript and recap are deleted after this many days. A job can only ask for less than the installation's limit, never for more. |
| **Pause merge** | On the job page, two sentences of the same speaker closer than this are shown as one turn. It changes how the transcript reads, not the transcript itself. |

### Summary detail

| Level | What the summary model is asked for |
|---|---|
| 1 | the 3 most important points, one short sentence each |
| 2 | about 5 points, one or two sentences each |
| 3 | about 8 points covering every main topic, two or three sentences each |
| 4 | about 12 points covering every topic discussed, a short paragraph each |
| 5 | every theme: one point per minute of recording, from 15 to 40, each a paragraph of four to six sentences |

A long transcript is read in parts of about 12,000 characters, and each
part is asked for its share of the points, so the whole recap keeps
about the length the level promises.

## Start

Press **Start job**. Voxtrama copies the files into the data folder,
checks them, and opens the job page, where you can
[follow the job](follow-a-job.md) as it runs.

If the button reads **A job cannot start yet**, the lines under it say
what is missing (usually the transcription model) and link to the
setting that fixes it.
