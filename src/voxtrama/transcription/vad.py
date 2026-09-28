"""Voice activity detection: the filter that is always on.

Whisper hallucinates on silence: it produces fluent, plausible text with a
real timestamp attached. For a product sold on verifiability, that is a
false claim carrying a valid piece of audio evidence. The VAD sits in front of
the ASR and decides what it is even allowed to see, and this module
exposes no switch to turn it off.

The four parameters below are a closed list, by the same names
faster-whisper's bundled Silero VAD expects as `vad_parameters`. The list
grows only by a design decision, not with a new field here.
"""

from __future__ import annotations

VAD_THRESHOLD = 0.5
MIN_SPEECH_DURATION_MS = 250
MIN_SILENCE_DURATION_MS = 700
SPEECH_PAD_MS = 200


def vad_parameters() -> dict[str, float | int]:
    """Return the fixed VAD parameters, ready for WhisperModel.transcribe."""
    return {
        "threshold": VAD_THRESHOLD,
        "min_speech_duration_ms": MIN_SPEECH_DURATION_MS,
        "min_silence_duration_ms": MIN_SILENCE_DURATION_MS,
        "speech_pad_ms": SPEECH_PAD_MS,
    }
