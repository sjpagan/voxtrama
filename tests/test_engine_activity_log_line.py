"""The run.log sentence for a generative step's windows."""

from __future__ import annotations

from voxtrama.engine.activity_log_line import activity_log_line


def test_windows_read_as_parts_not_as_a_clock() -> None:
    assert activity_log_line("writing the recap", "windows", 1, 4) == (
        "Writing the recap: 1 of 4 parts read"
    )


def test_audio_still_reads_as_a_clock() -> None:
    assert activity_log_line("transcribing", "seconds", 65, 600) == "Transcribing: 1:05 of 10:00"
