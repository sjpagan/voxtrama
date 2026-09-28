"""The language Whisper transcribes in, and its punctuated opening.

The recap's language is Whisper's language, unless the
first speech is clearly another. The model is transcription's fake: what
is under test is the choice, not faster-whisper's detection.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
from fakes.whisper_model import FakeWhisperModel
from faster_whisper.vad import VadOptions

from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.transcription import model_loading, transcribe
from voxtrama.transcription.language import OPENINGS, audio_language, initial_prompt


def _speechless(path: Path, seconds: float = 2.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x01\x00" * int(16_000 * seconds))


@pytest.fixture
def audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(model_loading, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(model_loading, "fetch_weights", lambda *args, **kwargs: None)
    monkeypatch.setattr(FakeWhisperModel, "detect_calls", 0)
    path = tmp_path / "recordings" / "rec1" / "call.wav"
    _speechless(path)
    return path


def _heard(monkeypatch: pytest.MonkeyPatch, language: str, probability: float) -> None:
    monkeypatch.setattr(FakeWhisperModel, "detected", (language, probability))


def _model() -> FakeWhisperModel:
    return FakeWhisperModel("small")


def test_the_chosen_language_is_used_when_the_audio_agrees(audio, monkeypatch) -> None:
    _heard(monkeypatch, "it", 0.97)
    assert audio_language(_model(), audio, "it") == "it"


def test_a_clearly_different_audio_language_wins(audio, monkeypatch) -> None:
    """An English recap asked of Italian speech: Whisper still hears Italian."""
    _heard(monkeypatch, "it", 0.95)
    assert audio_language(_model(), audio, "en") == "it"


def test_an_unsure_detection_leaves_the_chosen_language(audio, monkeypatch) -> None:
    _heard(monkeypatch, "es", 0.55)
    assert audio_language(_model(), audio, "it") == "it"


def test_detection_hears_speech_only_with_the_vad_as_an_object(audio, monkeypatch) -> None:
    """faster-whisper's detect_language reads the VAD options as attributes: a
    dict, which transcribe() accepts, fails there on real audio."""
    _heard(monkeypatch, "it", 0.97)
    audio_language(_model(), audio, "it")

    asked = FakeWhisperModel.last_detect_kwargs
    assert asked["vad_filter"] is True
    assert isinstance(asked["vad_parameters"], VadOptions)


def test_same_as_the_audio_uses_the_detected_language(audio, monkeypatch) -> None:
    _heard(monkeypatch, "fr", 0.6)
    assert audio_language(_model(), audio, None) == "fr"


def test_an_unsure_detection_without_a_choice_is_left_to_whisper(audio, monkeypatch) -> None:
    _heard(monkeypatch, "en", 0.3)
    assert audio_language(_model(), audio, None) is None


def test_no_audio_to_hear_keeps_the_choice(tmp_path: Path) -> None:
    missing = tmp_path / "missing.wav"
    assert audio_language(_model(), missing, "it") == "it"
    assert audio_language(_model(), missing, None) is None
    assert FakeWhisperModel.detect_calls == 0


def test_the_opening_comes_before_the_context() -> None:
    assert initial_prompt("it", "Voxtrama, Ollama") == OPENINGS["it"] + "\nVoxtrama, Ollama"
    assert initial_prompt("ja", "Voxtrama") == "Voxtrama"
    assert initial_prompt(None, None) is None


def test_every_opening_is_punctuated() -> None:
    for language, opening in OPENINGS.items():
        assert opening[0].isupper() and opening.endswith(".") and "," in opening, language


def test_transcribe_passes_the_language_and_its_opening(audio, monkeypatch) -> None:
    _heard(monkeypatch, "it", 0.99)
    recording = Recording(
        id="rec1",
        original_filename="call.wav",
        stored_path="recordings/rec1/call.wav",
        content_sha256="0" * 64,
        duration_seconds=2.0,
        media_format="wav",
    )

    transcribe(recording, "low", context="GP", language="it")

    asked = FakeWhisperModel.last_transcribe_kwargs
    assert asked["language"] == "it"
    assert asked["initial_prompt"] == OPENINGS["it"] + "\nGP"
    assert FakeWhisperModel.detect_calls == 1
