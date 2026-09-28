"""Which model weights a run will have to fetch, and which it will not."""

from __future__ import annotations

import pytest

from voxtrama.engine.downloads import pending_downloads
from voxtrama.workflow.definition import Step, Workflow


def _workflow(*skills: str) -> Workflow:
    return Workflow(
        name="w",
        version="1.0.0",
        schema_version="v1",
        description="test workflow",
        steps=[Step(id=skill, skill=skill, skill_version="1.0.0") for skill in skills],
    )


@pytest.fixture
def uncached(monkeypatch):
    """Nothing on disk: every weight set this run needs is still to download."""
    monkeypatch.setattr("voxtrama.engine.downloads.is_cached", lambda weights, models_dir: False)


@pytest.fixture
def cached(monkeypatch):
    monkeypatch.setattr("voxtrama.engine.downloads.is_cached", lambda weights, models_dir: True)


def test_a_transcribe_only_workflow_does_not_announce_the_speaker_model(uncached, tmp_path):
    """Warning about a download that never happens teaches people to ignore warnings."""
    pending = pending_downloads(_workflow("transcribe"), "low", tmp_path)

    assert [item.label for item in pending] == ["ASR model small"]


def test_a_workflow_that_diarises_announces_both(uncached, tmp_path):
    pending = pending_downloads(_workflow("transcribe", "diarize"), "low", tmp_path)

    assert [item.label for item in pending] == ["ASR model small", "speaker model ECAPA-TDNN"]


def test_nothing_is_announced_when_the_weights_are_already_there(cached, tmp_path):
    assert pending_downloads(_workflow("transcribe", "diarize"), "base", tmp_path) == []


def test_the_profile_decides_which_model_is_announced(uncached, tmp_path):
    pending = pending_downloads(_workflow("transcribe"), "base", tmp_path)

    assert pending[0].label == "ASR model medium"
    assert pending[0].nominal_bytes > 1024 * 1024 * 1024
