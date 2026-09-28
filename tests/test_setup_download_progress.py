"""setup.download_progress: the slot a model download publishes itself to."""

from __future__ import annotations

from pathlib import Path

from voxtrama.setup.download_progress import (
    IN_PROGRESS_STATES,
    publish_download_state,
    read_download_job_id,
    read_download_state,
    write_download_job_id,
)


def test_nothing_published_yet_reads_as_none(tmp_path: Path) -> None:
    assert read_download_state(tmp_path) is None
    assert read_download_job_id(tmp_path) is None


def test_a_published_state_reads_back_with_its_activity(tmp_path: Path) -> None:
    publish_download_state(
        tmp_path, "running", model_label="ASR model medium", done_bytes=512, total_bytes=1024
    )

    state = read_download_state(tmp_path)

    assert state.state == "running"
    assert state.activity.name == "ASR model medium"
    assert state.activity.done == 512
    assert state.activity.total == 1024


def test_the_job_id_sidecar_round_trips(tmp_path: Path) -> None:
    write_download_job_id(tmp_path, "abc-123")

    assert read_download_job_id(tmp_path) == "abc-123"


def test_queued_and_running_are_the_in_progress_states() -> None:
    assert IN_PROGRESS_STATES == {"queued", "running"}
    assert "succeeded" not in IN_PROGRESS_STATES
    assert "failed" not in IN_PROGRESS_STATES
