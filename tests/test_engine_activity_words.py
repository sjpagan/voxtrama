"""The live activity line names the step, not "processing audio"."""

from __future__ import annotations

from voxtrama.engine.activity_words import activity_message


def test_transcription_and_diarisation_say_what_they_do() -> None:
    assert activity_message("transcribe", "seconds", "audio") == "transcribing the audio"
    assert activity_message("diarize", "seconds", "audio") == "telling the speakers apart"


def test_a_download_inside_a_step_names_the_model() -> None:
    assert (
        activity_message("transcribe", "bytes", "ASR model small") == "downloading ASR model small"
    )


def test_a_step_nobody_named_keeps_the_generic_verb() -> None:
    assert activity_message("custom", "seconds", "audio") == "processing audio"
    assert activity_message("custom", "frames", "video") == "processing video"
