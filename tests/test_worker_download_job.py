"""worker.tasks.download_model_job: the background body the queue
now runs instead of a blocking POST (see api.routes.setup_processing's
2026-09-24 correction).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import voxtrama.worker.tasks as tasks
from voxtrama.config.settings import get_settings
from voxtrama.setup.download_progress import read_download_state


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point get_settings().data_dir at this test's own tmp_path."""
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_a_successful_download_publishes_running_then_succeeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_progress = []

    def _fake_fetch(weights, models_dir, on_progress):
        on_progress(100, weights.nominal_bytes)
        seen_progress.append((100, weights.nominal_bytes))

    monkeypatch.setattr(tasks, "fetch_weights", _fake_fetch)

    tasks.download_model_job("low")

    state = read_download_state(tmp_path)
    assert state.state == "succeeded"
    assert seen_progress  # on_progress was called through


def test_the_ecapa_key_resolves_to_the_speaker_model_not_a_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ECAPA is not a hardware profile. The same job now also
    accepts its own key, resolved to weights.ecapa_weights() rather than
    transcription.asr.weights_for() raising on an unknown profile.
    """
    seen = []

    def _fake_fetch(weights, models_dir, on_progress):
        seen.append(weights)

    monkeypatch.setattr(tasks, "fetch_weights", _fake_fetch)

    tasks.download_model_job(tasks.ECAPA_KEY)

    assert seen[0].label == "speaker model ECAPA-TDNN"
    assert seen[0].licence == "Apache-2.0"
    state = read_download_state(tmp_path)
    assert state.state == "succeeded"


def test_a_failed_download_publishes_failed_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_fetch(weights, models_dir, on_progress):
        raise OSError("disk full")

    monkeypatch.setattr(tasks, "fetch_weights", _broken_fetch)

    with pytest.raises(OSError):
        tasks.download_model_job("low")

    state = read_download_state(tmp_path)
    assert state.state == "failed"
    assert "disk full" in state.message
