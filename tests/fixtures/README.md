# Test fixtures

## `public-fixture.wav`

Thirteen seconds of scripted English conversation between two speakers, four
turns, 16 kHz mono, with `public-fixture.rttm` giving the exact interval of
each turn. Peak level sits at -3.4 dBFS: no sample clips, because a reference
clip other people measure against should not have any.

**This is the only audio file in the repository.** Everything else lives
outside it, under `VOXTRAMA_EVAL_DIR`, because real recordings carry the
voices of identifiable people and MIT publication cannot be undone.

### Licence

Nobody's voice was recorded. The clip is synthesized with
[Piper](https://github.com/OHF-Voice/piper1-gpl) (MIT) using two speakers of
the `en_US-libritts_r-medium` voice, trained on
[LibriTTS-R](https://www.openslr.org/141/), released under **CC BY 4.0**.

Attribution, as CC BY 4.0 requires: LibriTTS-R (Koizumi et al., 2023),
distributed by OpenSLR under CC BY 4.0. Piper voice packaging by the Piper
project.

### Regenerating it

A binary nobody can reproduce is opaque, so here is the exact recipe. The
transcript of what is said lives in `tools/eval/fixtures/cases.yaml`, under
the case id `public-fixture`.

```bash
docker run --rm -v "$PWD":/repo -w /repo -v "$PWD/.piper-voices":/voices \
  python:3.11-slim bash -c '
    apt-get update -qq && apt-get install -y -qq ffmpeg
    pip install -q pyyaml piper-tts
    python -m piper.download_voices --data-dir /voices en_US-libritts_r-medium
    python tools/eval/fixtures/generate.py \
      --only public-fixture --piper /voices --out /repo/tests/fixtures'
```

The `.rttm` is not transcribed after the fact: it is built from the timestamps
the clip is concatenated at, so it is exact by construction rather than by
annotation.

### What it is for

- the transcription test that would otherwise only run where
  `VOXTRAMA_EVAL_DIR` is set, and therefore never in CI;
- two separable speakers, so the same file serves diarization later.

Two distinct speaker ids of one multi-speaker model, rather than two separate
voices: one 79 MB download instead of two, and the pitch difference is wide
(roughly 179 Hz against 124 Hz median) so the two are genuinely separable.
