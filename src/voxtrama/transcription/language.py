"""The language Whisper transcribes in, and the opening that makes it punctuate.

The language chosen for the recap is the language Whisper
transcribes in, forced with `--language`. The earlier
default was `auto`, and on this 16-minute recording auto gave a transcript
with no punctuation and "viso studio code".

One safety net, because the new-job form starts from the browser's
language: an English recap asked of Italian speech must not force English
on Italian audio, where Whisper translates or makes words up. The first
speech is heard first (VAD on, up to DETECTION_SECONDS). If it is another
language with at least OVERRIDE_PROBABILITY, the audio's language wins.
With "Same as the audio" the detected language is the one used.

Whisper reads its initial prompt as the text said just before the audio,
and writes the way that text is written. large-v3 with
condition_on_previous_text=false and nothing before it often writes no
punctuation at all. A short punctuated opening in the language fixes the
style, and goes before the job's context, which is read last and so
weighs more.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from faster_whisper.vad import VadOptions

from voxtrama.transcription.vad import vad_parameters

DETECTION_SECONDS = 90
DETECTION_WINDOWS = 3  # of Whisper's 30 seconds each
OVERRIDE_PROBABILITY = 0.8
# Under this, with "Same as the audio", Whisper is left to detect on its own:
# a guess forced on the whole recording is worse than no answer.
DETECTED_PROBABILITY = 0.5

# Neutral on purpose: no topic, so the opening sets the style (sentences,
# commas, capitals) without steering the vocabulary.
OPENINGS = {
    "it": "Buongiorno a tutti. Bene, allora cominciamo: prima di tutto, grazie di essere qui.",
    "en": "Good morning, everyone. Well, let's begin: first of all, thank you for being here.",
    "es": "Buenos días a todos. Bien, empecemos: antes que nada, gracias por estar aquí.",
    "fr": "Bonjour à tous. Bien, commençons : tout d'abord, merci d'être là.",
    "de": "Guten Morgen zusammen. Gut, fangen wir an: Zuerst einmal danke, dass Sie hier sind.",
    "pt": "Bom dia a todos. Bem, vamos começar: antes de mais, obrigado por estarem aqui.",
    "nl": "Goedemorgen allemaal. Goed, laten we beginnen: allereerst bedankt dat jullie er zijn.",
}


def _first_seconds(audio_path: Path, sample_rate: int) -> np.ndarray:
    """The first DETECTION_SECONDS of `audio_path`, mono float32, never the whole file."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-t", str(DETECTION_SECONDS), "-i", str(audio_path),
         "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
        capture_output=True,
        check=False,
    )  # fmt: skip
    return np.frombuffer(result.stdout, dtype=np.float32)


def detect_language(model, audio_path: Path) -> tuple[str | None, float]:
    """The language of the first speech in `audio_path`, and how sure Whisper is."""
    audio = _first_seconds(audio_path, model.feature_extractor.sampling_rate)
    if audio.size == 0:
        return None, 0.0
    language, probability, _ = model.detect_language(
        audio=audio,
        vad_filter=True,
        # A VadOptions here, not the dict transcribe() accepts: detect_language
        # reads its fields as attributes (faster-whisper 1.2).
        vad_parameters=VadOptions(**vad_parameters()),
        language_detection_segments=DETECTION_WINDOWS,
    )
    return language, probability


def audio_language(model, audio_path: Path, wanted: str | None) -> str | None:
    """The language to transcribe `audio_path` in: `wanted`, unless the audio says otherwise.

    None when nothing could be heard clearly enough and the job chose
    no language: Whisper then detects on its own.
    """
    detected, probability = detect_language(model, audio_path)
    if wanted is None:
        return detected if probability >= DETECTED_PROBABILITY else None
    if detected is not None and detected != wanted and probability >= OVERRIDE_PROBABILITY:
        return detected
    return wanted


def initial_prompt(language: str | None, context: str | None) -> str | None:
    """The opening in `language`, then the job's context. None when there is neither."""
    parts = [part for part in (OPENINGS.get(language or ""), context) if part]
    return "\n".join(parts) or None
