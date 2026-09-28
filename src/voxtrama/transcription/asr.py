"""ASR: turns a Recording into a Transcript, via faster-whisper.

Every parameter here is fixed by the VAD/ASR configuration: the only
external input is which hardware profile selects the model.
transcription.vad's filter always runs: this module never asks
faster-whisper to skip it, since Whisper hallucinating on silence is the
defect this configuration exists to prevent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.transcript import Transcript
from voxtrama.humanize import human_clock
from voxtrama.ingest.cleanup import cleaned_audio
from voxtrama.transcription.language import audio_language, initial_prompt
from voxtrama.transcription.model_loading import load_model
from voxtrama.transcription.profiles import HardwareProfile, resolve_profile
from voxtrama.transcription.resources import resolve_engine_resources
from voxtrama.transcription.segments import build_segments
from voxtrama.transcription.vad import vad_parameters
from voxtrama.weights import whisper_weights

BEAM_SIZE = 5

# Fixed, not "latest". Pinned to the Hugging Face commit each
# converted model was published at, so the same profile gives the same
# result months apart. Grows only alongside a new entry in profiles.PROFILES.
_MODEL_REVISIONS = {
    "small": "536b0662742c02347bc0e980a01041f333bce120",
    "medium": "08e178d48790749d25932bbc082711ddcfdfbc4f",
    "large-v3": "edaa852ec7e145841d8ffdb056a99866b5f0a478",
}

logger = logging.getLogger(__name__)


def weights_for(profile: HardwareProfile):
    """The weight set a run on `profile` will need, before it needs it.

    Public so that an interface can say what a first run will download
    without starting one (the wait is announced beforehand).
    """
    model_profile = resolve_profile(profile)
    return whisper_weights(model_profile.model_size, _MODEL_REVISIONS[model_profile.model_size])


def _resolve_model(
    profile: HardwareProfile,
    settings: Settings,
    cores_per_chunk: int | None,
    parallel_chunks: int | None,
    on_download: Callable[[int, int | None], None] | None,
):
    """The ModelProfile for `profile`, the WhisperModel it loads, and the
    (cpu_threads, num_workers) it was loaded with.

    `cores_per_chunk`/`parallel_chunks` are already transcribe()'s
    resolution of a run's choice against Settings, never
    faster-whisper's defaults. transcription.resources's docstring covers
    the third level, this machine's tuning proposal, that
    resolve_engine_resources falls back to when both are still None. The
    pair is returned alongside the model so transcribe() can record on the
    Transcript what was used, not what was asked for: the two differ when a fallback fires.
    """
    model_profile = resolve_profile(profile)
    cpu_threads, num_workers = resolve_engine_resources(
        settings.data_dir, cores_per_chunk, parallel_chunks
    )
    model = load_model(
        model_profile.model_size,
        _MODEL_REVISIONS[model_profile.model_size],
        model_profile.compute_type,
        settings.models_dir,
        cpu_threads,
        num_workers,
        on_download,
    )
    return model_profile, model, cpu_threads, num_workers


def _run_whisper(model, audio_path: Path, wanted: str | None, context: str | None):
    """faster-whisper's own call, every parameter fixed but the language."""
    language = audio_language(model, audio_path, wanted)
    return model.transcribe(
        str(audio_path),
        language=language,  # the job's, unless the audio is clearly another
        beam_size=BEAM_SIZE,
        vad_filter=True,
        vad_parameters=vad_parameters(),
        condition_on_previous_text=False,
        word_timestamps=False,
        initial_prompt=initial_prompt(language, context),
    )


def transcribe(
    recording: Recording,
    profile: HardwareProfile,
    on_download: Callable[[int, int | None], None] | None = None,
    on_progress: Callable[[float, float | None], None] | None = None,
    cores_per_chunk: int | None = None,
    parallel_chunks: int | None = None,
    context: str | None = None,
    language: str | None = None,
) -> Transcript:
    """Run VAD-filtered ASR on `recording` and return the resulting Transcript.

    No Segment gets a person_id: diarisation comes after.
    `cores_per_chunk`/`parallel_chunks` are the run's choice, else Settings,
    else this machine's tuning; `language` is checked against the audio
    (transcription.language). Whisper reads the cleaned copy (ingest.cleanup).
    """
    settings = get_settings()
    audio_path = cleaned_audio(get_paths(settings.data_dir).data_dir / recording.stored_path)
    resolved_cores = cores_per_chunk if cores_per_chunk is not None else settings.cores_per_chunk
    resolved_parallel = parallel_chunks if parallel_chunks is not None else settings.parallel_chunks
    model_profile, model, cpu_threads, num_workers = _resolve_model(
        profile, settings, resolved_cores, resolved_parallel, on_download
    )

    raw_segments, info = _run_whisper(model, audio_path, language, context)
    logger.info(  # The opening line: what is transcribed, with what, on what
        "Transcribing %s of audio with whisper-%s, %d cores x %d in parallel, on this machine",
        human_clock(info.duration),
        model_profile.model_size,
        cpu_threads,
        num_workers,
    )

    transcript = Transcript(
        recording_id=recording.id,
        language=info.language,
        model_name=model_profile.model_size,
        model_revision=_MODEL_REVISIONS[model_profile.model_size],
        hardware_profile=profile,
        cpu_threads=cpu_threads,
        num_workers=num_workers,
        created_at=datetime.now(UTC),
    )
    transcript.segments = build_segments(raw_segments, info.duration, on_progress)
    return transcript
