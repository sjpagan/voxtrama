"""How progress is rendered, and what it must never do in a log file.

follow_run's own polling behaviour (terminal states, silence, giving up) is
tested separately in test_cli_follow_run.py, split out to stay under the
file-length threshold: rendering a line and deciding when to stop watching
are two different topics that happen to share this module.
"""

from __future__ import annotations

from voxtrama.cli.progress_view import ProgressPrinter
from voxtrama.engine.progress_file import Activity, ProgressState


def test_a_non_interactive_run_prints_no_control_characters(capsys):
    """A bar that rewrites its line is unreadable in a log: plain lines instead."""
    printer = ProgressPrinter(interactive=False)

    printer.render(ProgressState(run_id="r1", state="running", message="running transcribe"))
    printer.render(ProgressState(run_id="r1", state="running", message="running diarize"))

    output = capsys.readouterr().out
    assert "\r" not in output
    assert "\x1b" not in output
    assert output.splitlines() == ["running transcribe", "running diarize"]


def test_an_interactive_run_rewrites_one_line(capsys):
    printer = ProgressPrinter(interactive=True)

    printer.render(ProgressState(run_id="r1", state="running", message="running transcribe"))

    assert "\r" in capsys.readouterr().out


def test_the_same_state_twice_prints_once(capsys):
    """The file is polled several times a second. Only changes are worth a line."""
    printer = ProgressPrinter(interactive=False)
    state = ProgressState(run_id="r1", state="running", message="running transcribe")

    printer.render(state)
    printer.render(state)

    assert capsys.readouterr().out.count("running transcribe") == 1


def test_a_download_is_shown_with_both_numbers(capsys):
    printer = ProgressPrinter(interactive=False)

    printer.render(
        ProgressState(
            run_id="r1",
            state="running",
            activity=Activity(
                name="ASR model small",
                unit="bytes",
                done=242 * 1024 * 1024,
                total=484 * 1024 * 1024,
            ),
        )
    )

    output = capsys.readouterr().out
    assert "242 MB of 484 MB" in output
    assert "50%" in output


def test_a_position_in_seconds_is_shown_as_a_clock(capsys):
    printer = ProgressPrinter(interactive=False)

    printer.render(
        ProgressState(
            run_id="r1",
            state="running",
            activity=Activity(name="audio", unit="seconds", done=724, total=1110),
        )
    )

    assert "processing audio: 12:04 / 18:30" in capsys.readouterr().out


def test_the_step_position_is_shown(capsys):
    printer = ProgressPrinter(interactive=False)

    printer.render(
        ProgressState(
            run_id="r1", state="running", step_total=2, step_index=1, message="running diarize"
        )
    )

    assert "[2/2] running diarize" in capsys.readouterr().out


def test_two_steps_measuring_the_same_audio_do_not_read_alike(capsys):
    """transcribe and diarize both report seconds of the same recording.

    Without the step position in front, "processing audio: 1:01 / 18:30"
    says the same thing whether transcription just restarted or
    diarisation has begun, which is the question this exists to answer.
    """
    printer = ProgressPrinter(interactive=False)
    audio = dict(name="audio", unit="seconds", total=1110.0)

    printer.render(
        ProgressState(
            run_id="r1",
            state="running",
            step_total=3,
            step_index=0,
            activity=Activity(done=61.5, **audio),
        )
    )
    printer.render(
        ProgressState(
            run_id="r1",
            state="running",
            step_total=3,
            step_index=1,
            activity=Activity(done=61.5, **audio),
        )
    )

    printed = capsys.readouterr().out.strip().splitlines()
    assert printed == [
        "[1/3] processing audio: 1:01 / 18:30",
        "[2/3] processing audio: 1:01 / 18:30",
    ]
