"""The progress file: what the engine publishes and the CLI reads back."""

from __future__ import annotations

import json

from voxtrama.engine.progress_file import (
    Activity,
    ProgressState,
    progress_path,
    read_progress,
    write_progress,
)


def test_a_published_state_reads_back_unchanged(tmp_path):
    state = ProgressState(
        run_id="r1", state="running", step_total=2, step_index=0, step_id="transcribe"
    )

    write_progress(tmp_path, state)

    read = read_progress(tmp_path, "r1")
    assert read is not None
    assert (read.state, read.step_index, read.step_id) == ("running", 0, "transcribe")


def test_an_activity_survives_the_round_trip(tmp_path):
    """Bytes, not a percentage: 63% of 480 MB and of 3 GB are different waits."""
    state = ProgressState(
        run_id="r1",
        state="running",
        activity=Activity(name="ASR model small", unit="bytes", done=1024, total=4096),
    )

    write_progress(tmp_path, state)

    read = read_progress(tmp_path, "r1")
    assert read is not None and read.activity is not None
    assert read.activity.done == 1024
    assert read.activity.total == 4096


def test_an_old_progress_file_reads_as_none_not_a_crash(tmp_path):
    """A run caught mid-upgrade may have written the old `download` key.

    read_progress must not raise on it: the run keeps going, and whoever is
    watching just sees no state for a moment.
    """
    path = progress_path(tmp_path, "r1")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "r1",
                "state": "running",
                "step_total": 0,
                "step_index": None,
                "step_id": None,
                "message": None,
                "download": {"name": "ASR model", "downloaded_bytes": 1024, "total_bytes": None},
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        )
    )

    assert read_progress(tmp_path, "r1") is None


def test_the_file_lives_in_the_run_own_folder(tmp_path):
    """A run is a folder you can open, while it runs and after."""
    write_progress(tmp_path, ProgressState(run_id="r1", state="running"))

    assert progress_path(tmp_path, "r1").parent.name == "r1"


def test_a_rewrite_is_never_seen_half_written(tmp_path):
    """Written to a temporary file and renamed: a reader sees old or new, never both."""
    write_progress(tmp_path, ProgressState(run_id="r1", state="running", message="first"))
    write_progress(tmp_path, ProgressState(run_id="r1", state="running", message="second"))

    payload = json.loads(progress_path(tmp_path, "r1").read_text())
    assert payload["message"] == "second"
    assert list(progress_path(tmp_path, "r1").parent.iterdir()) == [progress_path(tmp_path, "r1")]


def test_a_missing_file_reads_as_none(tmp_path):
    assert read_progress(tmp_path, "never-ran") is None


def test_a_corrupt_file_reads_as_none_instead_of_raising(tmp_path):
    """A broken progress file must never be why a finished run looks failed."""
    path = progress_path(tmp_path, "r1")
    path.parent.mkdir(parents=True)
    path.write_text("{ this is not json")

    assert read_progress(tmp_path, "r1") is None
