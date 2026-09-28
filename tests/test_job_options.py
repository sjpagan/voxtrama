"""The new-job form's own options reaching the work: the declared
context becomes Whisper's initial prompt, the 1-5 detail a sentence
in the summarize prompt, and all three land in the manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.whisper_model import FakeWhisperModel

from voxtrama.config.settings import Settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.transcript import Segment
from voxtrama.engine.generative_windows import fill_prompt
from voxtrama.engine.summary_detail import DETAIL_INSTRUCTIONS, detail_instruction
from voxtrama.engine.transcript_windows import split_windows, window_text
from voxtrama.manifest.choices import choices_info
from voxtrama.transcription import model_loading, transcribe
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.skill_file import load_skill_file

_SUMMARIZE = Path(__file__).resolve().parents[1] / "skills" / "summarize.yaml"


@pytest.fixture
def fake_whisper(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeWhisperModel.last_transcribe_kwargs = None
    monkeypatch.setattr(model_loading, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(model_loading, "fetch_weights", lambda *args, **kwargs: None)


def _recording() -> Recording:
    return Recording(
        id="rec1",
        original_filename="call.wav",
        stored_path="recordings/rec1/call.wav",
        content_sha256="0" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )


@pytest.mark.usefixtures("fake_whisper")
def test_the_declared_context_is_whisper_s_initial_prompt() -> None:
    transcribe(_recording(), "low", context="Voxtrama, Ollama, GP")

    assert FakeWhisperModel.last_transcribe_kwargs["initial_prompt"] == "Voxtrama, Ollama, GP"


@pytest.mark.usefixtures("fake_whisper")
def test_no_context_transcribes_without_a_prompt() -> None:
    transcribe(_recording(), "low")

    assert FakeWhisperModel.last_transcribe_kwargs["initial_prompt"] is None


def test_the_summarize_prompt_carries_the_chosen_detail() -> None:
    template = load_skill_file(_SUMMARIZE).prompt
    segments = [Segment(start=0.0, end=1.0, text="We ship on Friday.")]

    text = window_text(segments, split_windows(segments)[0], 1)
    prompt = fill_prompt(template, text, "English", detail_instruction(5))

    assert DETAIL_INSTRUCTIONS[5].format(points=15) in prompt
    assert "We ship on Friday." in prompt


def test_a_detail_out_of_range_is_clamped_not_a_broken_prompt() -> None:
    assert detail_instruction(9) == detail_instruction(5)
    assert detail_instruction(0) == DETAIL_INSTRUCTIONS[1]


def test_the_manifest_records_the_job_s_own_options() -> None:
    choices = RunChoices(context="Voxtrama", summary_detail=4, pause_merge_seconds=2.0)

    info = choices_info(choices)

    assert (info.context, info.summary_detail, info.pause_merge_seconds) == ("Voxtrama", 4, 2.0)


def test_the_installation_defaults_are_three_and_one_and_a_half_seconds() -> None:
    settings = Settings()

    assert (settings.summary_detail, settings.pause_merge_seconds) == (3, 1.5)
