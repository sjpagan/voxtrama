"""reuse_key and the new-job form's choices: a regenerated job must redo the
step a changed choice steers, and only that step."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voxtrama.engine import step_hashing
from voxtrama.workflow.choices import RunChoices


@pytest.fixture(autouse=True)
def _same_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(step_hashing, "input_sha256", lambda step, context: "same")


def _key(skill: str, **choices: object) -> str:
    step = SimpleNamespace(id=skill, skill=skill, skill_version="1.0.0")
    context = SimpleNamespace(choices=RunChoices(**choices), kept_local={})
    return step_hashing.reuse_key(step, context)  # type: ignore[arg-type]


def test_the_context_redoes_the_generative_steps_not_the_transcript() -> None:
    """A corrected context changes the next
    results, not the transcript already made."""
    assert _key("summarize") != _key("summarize", context="Weekly sync")
    assert _key("extract_decisions") != _key("extract_decisions", context="Weekly sync")
    assert _key("transcribe") == _key("transcribe", context="Weekly sync")
    assert _key("diarize") == _key("diarize", context="Weekly sync")


def test_another_transcription_model_redoes_the_transcript() -> None:
    assert _key("transcribe", hardware_profile="low") != _key("transcribe", hardware_profile="high")


def test_the_detail_changes_summarize_only() -> None:
    assert _key("summarize", summary_detail=2) != _key("summarize", summary_detail=4)
    assert _key("transcribe") == _key("transcribe", summary_detail=4)


def test_no_choice_keeps_the_key_it_always_had() -> None:
    step = SimpleNamespace(id="s", skill="summarize", skill_version="1.0.0")
    context = SimpleNamespace(choices=RunChoices(), kept_local={})
    assert step_hashing._choices_read_by(step, context) == {}  # type: ignore[arg-type]
