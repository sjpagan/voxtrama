# Read and check the results

A finished job opens on its job page: the head of the job, an audio player and five tabs. Switching tab does not reload the page, so the audio keeps playing.

## The five tabs

| Tab | What it holds |
|---|---|
| **Transcript** | the transcript as speaker turns, beside the **Verified output** cards linked to the passages they quote |
| **Explore** | every sentence on one line, with its time and speaker, to search and to correct one sentence |
| **Speakers** | the voices Voxtrama told apart, to listen to and name; see [Speakers](speakers.md) |
| **Recap** | the points of the recap and of the extractions, with their source and provenance |
| **Files** | the downloads of the job; see [Export](export.md) |

The page opens on the **Recap** tab when the job has a recap, and on the **Transcript** tab when it has none, as after **Transcribe only**. The **Speakers** tab is missing when the job's audio has been deleted, because there is nothing left to listen to.

## The head

The title is the job name. The line under it says what the job ran with. Each part appears only when it applies.

| Part of the line | Meaning |
|---|---|
| the workflow | for example **Meeting decisions** |
| **Whisper** and a size | the transcription model, such as Whisper large-v3 |
| the summary model | the model that wrote the recap |
| **Detail 3/5** | the summary detail level |
| **8 cores** | the cores the job used |
| **Context** with a check mark | someone wrote a context for the job |
| **Context deduced** | nobody did, and Voxtrama deduced one from the transcript: who speaks, about what, which names and acronyms recur. Open it to read it. The transcript wins where the two differ. |
| **N windows of ~12k characters** | the transcript was long enough to be read in parts of about 12,000 characters, and the results were joined |
| **Deleted on** a date, or **Kept N days** | shown only when a retention limit applies to the job |

The chain of steps under the head shows how long each step took. A step reused from an earlier job says **Reused**; see [Correct and regenerate](correct-regenerate.md).

## The player

The player has these controls:

| Control | What it does |
|---|---|
| **«60s**, **«10s** | jumps back 60 or 10 seconds |
| play and pause | starts and stops the audio |
| **10s»**, **60s»** | jumps forward 10 or 60 seconds |
| the time, such as 4:12 / 28:17 | the position and the length |
| the waveform | click to jump to a moment; with the waveform focused, the arrow keys move 5 seconds at a time |
| the volume slider | sets the volume |
| the **⋮** menu | **Download audio** |

If the waveform cannot be drawn, the player says "No waveform for this recording. Playback works as usual." Every time shown on the page, such as a sentence in the transcript or a point in the recap, is a button that plays the audio from there. A match found by a search moves the player to the match without starting it.

## Recap

![The Recap tab](images/job-recap.png)

The **Recap** tab has one section per kind of result: **Key points**, then **Decisions**, **Concepts** or **Themes**, depending on the workflow. Each point shows the speaker and the time of the quote it rests on, for example "Alex · 4:12". Each section ends with its provenance: the workflow, the skill and the model that wrote it, separated by dots.

**Search recap** finds a word in the recap, shows "2 of 5" and moves between the matches with the arrows. The search runs in the page; what you type is not sent to the server.

A job made with **Transcribe only** has no recap, and the tab says "This job produced a transcript only, with no recap."

### Needs review

**Needs review** marks a point whose quote Voxtrama could not find in the transcript. This check is what makes a recap verifiable.

Every point the summary model writes must come with a quote from the transcript. Voxtrama then looks for that quote itself, in the text of the transcript, ignoring case and extra spaces but not punctuation:

- the quote is found once: the point shows the speaker and the time, and pressing it plays the passage;
- the quote is not found, or occurs more than once so that its place is ambiguous: the point is marked **Needs review** and has no time. The model may have paraphrased, or written something that was never said.

Voxtrama never trusts a timestamp written by the summary model, since a model asked for one invents plausible ones. It finds the quote by itself. A point that needs review never fails the job; it is shown and marked.

A point you corrected by hand shows **Edited**; see [Correct and regenerate](correct-regenerate.md).

#### Check a point against the audio

1. Open the **Recap** tab and find a point you want to rely on.
2. If it shows a speaker and a time, press that button.

    You should see: the player jumping to that moment and playing. Listen to the passage and judge whether the point says what was said.

3. If the point is marked **Needs review**, search the transcript instead. Open the **Transcript** tab or the **Explore** tab, type a distinctive word of the point in **Search transcript**, and press the arrows to move between the matches.

    You should see: the matches marked in the text and the player moved to each match, without starting. Press the time of a match to play it.

4. If you find the passage, you can tie the point to it: in the **Transcript** tab, under the point's card, open **Edit or link to another turn**, choose the turn in **Evidence** and press **Save**.

    You should see: the point marked **Edited**, with its time, and no longer **Needs review**.

5. If you do not find the passage, do not use the point.

## Transcript

![The Transcript tab, with each point of the recap tied to its passage](images/job-transcript.png)

The **Transcript** tab shows one bubble per speaker turn, the first speaker on the left and the second on the right, with the **Verified output** beside it. Each card of the **Verified output** shows its kind (**Key point**, **Decision**, **Concept** or **Theme**), the time of its evidence, its text and, at the foot, either **Evidence** with the speaker and the time, or **No evidence**. The card also carries **Needs review** or **Edited** when they apply.

- Press an **Evidence** button: the player jumps there and the turns the evidence covers are highlighted.
- Select a turn: the cards that come from it are highlighted, and a line says how many results come from the passage you selected.
- **Merge pauses under** joins the sentences of one speaker separated by less than this many seconds, from 0.5 to 5, into one turn. It changes the reading, not the transcript. **Original segments** opens the sentences a turn is made of.
- **Search transcript** finds a word and moves between the matches.

A notice at the top of the Transcript tab says "Speaker names are assigned automatically and may occasionally be wrong." The name on each bubble only says who speaks. Names are given in the **Speakers** tab, and one sentence is given to someone else in the **Explore** tab. See [Speakers](speakers.md).

To correct a point of the **Verified output**, see [Correct and regenerate](correct-regenerate.md).

## Explore

![The Explore tab](images/job-explore.png)

The **Explore** tab lists every sentence with its time and speaker, one per line. Search the whole recording with **Search transcript**, or filter one speaker with **All speakers**, a list that appears when the job has more than one speaker. Click a line, or press Enter on it, to play from there. When a filter is on, the search looks only at the lines still shown.

To give one sentence to someone else, see [Speakers](speakers.md).

## Related pages

- [Speakers](speakers.md)
- [Correct and regenerate](correct-regenerate.md)
- [Export](export.md)
- [Follow a job](follow-a-job.md)
