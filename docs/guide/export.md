# Export

Voxtrama exports the recap as PDF, HTML or DOCX, the transcript as TXT, Markdown, JSON or JSONL, the record of the job as `manifest.json`, and everything together as one ZIP. All downloads are plain links on the job page, and they are built on this machine.

## Export the recap

1. Open a finished job on its **Recap** tab.
2. Press **Export**.

    You should see: a menu with **PDF**, **HTML**, **DOCX** and **Manifest (JSON)**.

3. Choose a format.

    You should see: a file named after the job in your downloads folder.

The three recap formats say the same thing in the same order: the job's name, a line with what the job ran with, then every section with its points. Each point carries its source, written as the speaker and the time in parentheses, and **Needs review** in brackets when it applies. Each section ends with its provenance line. A point you corrected by hand is exported with the corrected text.

A job made with **Transcribe only** has no recap, and the recap formats are not offered.

## Export the record of the job

**Manifest (JSON)** saves `manifest.json`, the job's record: which models ran, with which settings, on which file. It is the file to share or archive when someone asks how a result was made.

The downloaded copy is made to be shared. Voxtrama replaces these fields with `[removed]`:

| Field | Why |
|---|---|
| the context you wrote | it can name people and projects |
| the deduced context | a deduced context names people too |
| the address (host) of every model server, in the steps and in error messages and failure messages that name it | a host maps the network behind it |

The copy kept in the data folder keeps everything. [Taking your data with you](data-portability.md) describes the manifest.

## The Files tab

The **Files** tab lists every file the job produced, one row each, with one button per format.

| Row | What it holds | Buttons |
|---|---|---|
| **Everything** | One ZIP: the manifest, the transcript, and the recording in parts of about ten minutes, each part's audio next to its text | **ZIP** |
| **Transcript** | The whole transcript, with times and speakers | **TXT**, **Markdown**, **JSON**, **JSONL** |
| **Recap** | The recap as the **Recap** tab shows it; shown only when the job has a recap | **PDF**, **HTML**, **DOCX** |
| **Manifest** | What the job ran with, without the context you wrote | **JSON** |
| **Recording** | The audio as it was uploaded; shown only while the audio exists | **Audio** |

### Transcript formats

| Format | Content |
|---|---|
| **TXT** | one line per sentence, like `[12:04] Anna: text` |
| **Markdown** | a heading with the job's name, then one paragraph per sentence with its time and speaker in bold |
| **JSON** | the title and every sentence with its start and end in seconds, its speaker and its text, for another program to read |
| **JSONL** | one JSON object per line and sentence, for scripts and search indexes |

### The ZIP

The ZIP of the **Everything** row holds:

| File | Content |
|---|---|
| `manifest.json` | what the job ran with, with the context text and the hosts removed |
| `transcript.txt`, `transcript.md`, `transcript.json`, `transcript.jsonl` | the whole transcript in the four formats |
| `parts/` | the job in parts of about ten minutes: for each part, an MP3 of its audio and a `.txt` with its text |
| `README.txt` | what each file is, and the time range of each part |

Parts let you work on a long call a piece at a time. When the recording is gone, or ffmpeg cannot cut it on this machine, the ZIP still holds the text of each part, and `README.txt` says that the recording was not available.

The ZIP is built in a temporary folder and removed once it is sent: nothing is added to the data folder.

## Download the audio

The **Recording** row, and the **⋮** menu of the player with **Download audio**, give the audio as it was uploaded. For a job made of several files, that is the joined or mixed FLAC; see [Start a job](new-job.md).

## Related pages

- [Read and check the results](results.md)
- [Correct and regenerate](correct-regenerate.md)
- [Taking your data with you](data-portability.md)
- [Privacy and data](privacy.md)
