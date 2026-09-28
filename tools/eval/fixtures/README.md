# Eval fixtures

Synthetic audio fixtures for diarization evaluation and VAD/ASR
evaluation. Each fixture is a short, scripted multi-speaker
conversation synthesized with the ElevenLabs text-to-speech API, concatenated
with exact, known timing, so the resulting RTTM is ground truth by
construction rather than by manual annotation.

## Not part of Voxtrama

This is a development tool. **ElevenLabs is not a dependency of the product**
and never will be: it is not installed by Voxtrama, not called at runtime, and
does not appear in THIRD_PARTY_LICENSES.md. It exists here so that
development has multi-speaker audio in several languages whose ground truth is
known exactly.

The generated audio stays outside the repository, under the data directory
(`~/Voxtrama/eval/` by default). Nothing produced by this tool is redistributed.

In production, calibration works the other way round: the person installing
Voxtrama reads a short script out loud and the system measures its own
transcription against that known text. No third-party
voice service is involved on a user's machine.

## Running it

```
python tools/eval/fixtures/generate.py --dry-run
```

`--dry-run` never calls ElevenLabs: it replaces every turn with an ffmpeg sine
tone (one frequency per voice) of the same estimated duration, so the whole
pipeline (overlap placement, effects, RTTM, metadata) can be exercised for
free. Use it to develop against this tool and to run `test_generate.py`.

Without `--dry-run`, every turn is synthesized by ElevenLabs and **spends the
caller's ElevenLabs credit**. Only run it once `voices.yaml` has real voice
ids (see below).

Options:

- `--cases <path>`: manifest to read (default: `cases.yaml` next to this script).
- `--only <id>`: generate a single case instead of all of them.
- `--out <dir>`: output directory (default: `~/Voxtrama/eval/`).
- `--dry-run`: synthesize sine tones instead of calling ElevenLabs.

## What it produces

For every case in `cases.yaml`, under `--out`:

- `<id>.wav`: mono, 16 kHz PCM, the full conversation.
- `<id>.rttm`: one `SPEAKER` line per turn, standard RTTM format, with
  start and duration taken directly from the timeline the audio was built
  from.
- `<id>.json`: language, speaker count, duration, effects applied, a
  SHA-256 of the wav, and an explicit note that the material is synthetic.

## Configuring voices

`voices.yaml` maps a logical voice name (referenced from `cases.yaml`) to an
ElevenLabs `voice_id`, plus its language and gender. Every `voice_id` ships as
the placeholder `REPLACE_WITH_ELEVENLABS_VOICE_ID`; pick real voices from your
ElevenLabs account and fill them in. Running without `--dry-run` while a
voice still has the placeholder id fails immediately with a clear error,
before any network call is made for that case.

The API key is read from `ELEVENLABS_API_KEY`, or from
`~/.config/elevenlabs/key` if that variable is unset.

## Limits of this synthetic material

This material calibrates the pipeline and acts as a regression gate. It is
**not** a substitute for real recordings, and the choice of diarization
backend (#2) must be decided against those, not against this fixture set.
Specifically:

- **Overlap** is produced by summing two independently synthesized tracks at
  a fixed offset. It does not reproduce how humans actually interrupt each
  other: no Lombard effect (speakers raising their voice over one another),
  no room crosstalk, no timing drift from a real back-and-forth.
- **Noise** is added on top of the mix at a declared SNR. It is not a
  recording made in a noisy room: there is no reverberation, no directional
  effect, and the noise floor is perfectly stationary.
- **The telephone chain** (`telephone-8k`) is a codec (8 kHz resample,
  mu-law encode, resample back to 16 kHz) applied to an already-clean
  signal. It has none of what a real phone call adds: no jitter, no packet
  loss, no line noise, no echo.

Treat a good score on this set as "the pipeline didn't regress", not as "this
will hold up on a real meeting recording".
