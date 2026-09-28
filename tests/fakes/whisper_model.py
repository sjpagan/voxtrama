"""A stand-in for faster_whisper.WhisperModel: records the keyword
arguments its constructor received instead of loading gigabytes of real
weights, and .transcribe() hands back no segments over a fixed duration:
enough for a test that checks what transcription.model_loading passes
down, not what faster-whisper itself would produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeFeatureExtractor:
    sampling_rate: int = 16_000


@dataclass
class FakeTranscribeInfo:
    language: str = "en"
    duration: float = 1.0


class FakeWhisperModel:
    """`last_kwargs` lives on the class, not the instance: load_model
    returns the instance to its caller, so a test asserting on how it was
    built has no reference of its own to read it from.
    """

    last_kwargs: dict[str, Any] | None = None
    # What .transcribe() itself was asked, e.g. the declared context.
    last_transcribe_kwargs: dict[str, Any] | None = None
    # What .detect_language() answers, and whether it was asked.
    detected: tuple[str, float] = ("en", 1.0)
    detect_calls: int = 0
    last_detect_kwargs: dict[str, Any] | None = None
    feature_extractor = FakeFeatureExtractor()

    def __init__(self, model_size_or_path: str, **kwargs: Any) -> None:
        self.model_size_or_path = model_size_or_path
        FakeWhisperModel.last_kwargs = {"model_size_or_path": model_size_or_path, **kwargs}

    def detect_language(self, audio: Any = None, **kwargs: Any) -> tuple[str, float, list]:
        FakeWhisperModel.detect_calls += 1
        FakeWhisperModel.last_detect_kwargs = kwargs
        language, probability = FakeWhisperModel.detected
        return language, probability, [(language, probability)]

    def transcribe(self, *args: Any, **kwargs: Any) -> tuple[list[Any], FakeTranscribeInfo]:
        FakeWhisperModel.last_transcribe_kwargs = kwargs
        return [], FakeTranscribeInfo()
