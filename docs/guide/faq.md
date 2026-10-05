# FAQ

Each answer is short, and links to the page that has the details.

## Can I transcribe and summarize meetings locally with Whisper and Ollama?

Yes. Voxtrama transcribes a recording with Whisper on your processor, tells the speakers apart, and asks a summary model served by Ollama for a recap, decisions, themes or concepts. Everything can run on one machine. [Your first job](first-job.md) walks through it, and [Set up the summary model](summary-model-setup.md) installs Ollama.

## Is there a self-hosted web interface for Whisper with speaker diarization in Docker?

Yes. Voxtrama runs in Docker on your machine and serves its web interface at `127.0.0.1`. It tells speakers apart inside each recording (speaker diarization) and lets you name them in the **Speakers** tab. See [Requirements](requirements.md) and [Speakers](speakers.md).

## Does Voxtrama work offline?

Yes, once its models are downloaded. The transcription model and the speaker model are downloaded from Hugging Face the first time they are needed. After that, a job needs no network when the summary model runs on the same machine. See [Privacy and data](privacy.md).

## Does my audio leave my machine?

No, unless you configure a remote model server. Transcription and speaker diarization always run inside Voxtrama. The transcript and the context you wrote are sent out only to a remote model server, and a step marked `local_only` is refused before anything is sent. See [Privacy and data](privacy.md).

## Is Voxtrama GDPR compliant?

Compliance depends on how a deployment is run, and Voxtrama alone cannot give it. What Voxtrama provides is facts you can assess: data stays in one folder you control, nothing leaves the machine unless you configure a remote server, no voice print is stored, and retention deletes old jobs. [Privacy and data](privacy.md) lists them. It is not legal advice.

## Does Voxtrama keep voice prints or recognise a speaker across recordings?

No. Voxtrama tells speakers apart inside one recording and keeps no voice print. A voice print is biometric data, and keeping it would turn a transcription tool into an identification system. You name speakers by hand. See [Speakers](speakers.md) and [Privacy and data](privacy.md).

## How many speakers can it tell apart?

Up to 4 by default. `VOXTRAMA_MAX_SPEAKERS` raises or lowers the ceiling. Speakers are told apart automatically and can be wrong, so check them in the **Speakers** tab. See [Configuration](configuration.md) and [Troubleshooting](troubleshooting.md).

## Does it need a Hugging Face token or pyannote?

No. Voxtrama does not use pyannote, and its code passes no Hugging Face token. The speaker model is `speechbrain/spkrec-ecapa-voxceleb`. See [Configuration](configuration.md).

## Does Voxtrama handle long recordings, and does Whisper hallucinate on silence?

Yes to the first. A job's time budget is computed from the length of the audio, and an upload is limited by its size (8192 MB by default) and by the free space. For silence, a voice activity filter is always on, with no switch to turn it off, so stretches without speech are not given to Whisper. A transcript too long for the summary model is read in parts of about 12 000 characters. See [Summary models and servers](model-servers.md) and [Start a job](new-job.md).

## How fast is it on a CPU?

Speed depends on your machine. As one example, on an Intel Xeon W-2150B with 64 GB of RAM, using the `high` profile (Whisper large-v3, 4 cores per chunk, 2 chunks in parallel), 21 minutes of audio took 7 minutes 30 seconds to transcribe and 2 minutes 38 seconds to separate the speakers. Yours may be faster or slower. Use `voxtrama doctor` and [Troubleshooting](troubleshooting.md) to tune the profile and the cores.

## Does Voxtrama use a GPU?

No, not for transcription. The Voxtrama image is CPU only. A summary model can use a graphics card when the Ollama server that runs it has one. See [Requirements](requirements.md) and [Summary models and servers](model-servers.md).

## Why is Docker on macOS slow, and can it use the GPU?

Docker on macOS gives containers no access to the graphics card, and Voxtrama transcribes on the processor in any case. How fast a job runs depends on the processor, on the transcription profile and on the cores a job uses. The **Efficient** and **Balanced** profiles are faster than **Maximum accuracy**. See [Troubleshooting](troubleshooting.md).

## Which platforms does it run on?

Voxtrama 0.1 has been tested end to end on macOS with an Intel processor. Linux and Apple Silicon have not been tested end to end yet, and Windows is not supported yet. See [Requirements](requirements.md).

## Which audio formats and sizes does it accept?

It accepts audio and video files in these containers: WAV, W64, RF64, MP3, FLAC, Ogg, MOV, MP4, M4A, Matroska, WebM, AAC, AIFF, CAF, ASF, AMR, AVI, MPEG, MPEG-TS and WavPack. The limit is 8192 MB per upload by default, set by `VOXTRAMA_MAX_UPLOAD_MB`, and it applies to the whole request. It is Voxtrama's own limit and has nothing to do with the 25 MB limit of an online transcription API. See [Troubleshooting](troubleshooting.md) and [Configuration](configuration.md).

## Can the recap invent quotes?

A summary model can, and Voxtrama checks for it. Every point of a recap carries a quote, and Voxtrama looks for the quote in the transcript. A point whose quote is not found is marked **Needs review** and is not shown as fact. Each point links to the moment in the audio, so you can play it back. See [Read and check the results](results.md).

## What if the summary model's context window is too short?

A step can fail. Voxtrama reads a long transcript in parts of about 12 000 characters, and a context limit lower than a part needs makes the step fail with a message that the prompt did not fit. Raise **Use at most** to the model's maximum, or choose a model with a larger window. See [Summary models and servers](model-servers.md).

## Can I run it without a summary model?

Yes. Tick **Transcription only, no summary** in the **Advanced** section of the new-job form. The job produces the transcript and the speakers. Without any summary model, a job that needs a recap fails at that step and keeps the transcript. See [Summary models and servers](model-servers.md).

## Which languages does it support?

Voxtrama uses the multilingual Whisper models small, medium and large-v3, and transcribes in the language you choose or the one it detects. The recap can be written in Italian, English, Spanish, French, German, Portuguese or Dutch. See [Start a job](new-job.md).

## Does it work in real time or with a microphone?

No. Voxtrama processes finished recordings and not a live microphone. See [Your first job](first-job.md).

## Does it work with OpenAI-compatible servers?

No. In 0.1, Voxtrama talks to a model server through Ollama's own API. It does not call the OpenAI API. See [Summary models and servers](model-servers.md).

## Can I download audio from a video site with it?

No. Voxtrama works on files you already have. See [Start a job](new-job.md).

## How do I reproduce a job, or compare two?

Every job writes a `manifest.json` that records which models ran, with which settings, on which file. A job can be regenerated with other choices, and the steps whose inputs did not change are reused. `voxtrama compare` reports the differences between two manifests. See [Correct and regenerate](correct-regenerate.md) and [Command line](cli.md).

## How do I delete my data?

Delete a job from the Jobs page, or set a retention limit. **Delete** removes what you tick, among the audio, the transcript and the recap. Retention deletes finished jobs after 7, 30, 90 or 365 days, and `voxtrama retention` checks that nothing of them is left. See [Privacy and data](privacy.md) and [Jobs, search and clean-up](jobs.md).

## How do I move Voxtrama to another machine?

Copy the data folder, without `models/`, and start Voxtrama on the other machine. See [Taking your data with you](data-portability.md).

## Related pages

- [Requirements](requirements.md)
- [Privacy and data](privacy.md)
- [Troubleshooting](troubleshooting.md)
- [Command line](cli.md)
