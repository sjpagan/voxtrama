"""follow_run's own polling behaviour: when it stops, and why.

Split from test_cli_progress.py to stay under the file-length threshold:
that file is what a single line looks like, this is when follow_run decides
to stop watching for one.
"""

from __future__ import annotations

from voxtrama.cli.progress_view import follow_run
from voxtrama.engine.progress_file import ProgressState, write_progress


def test_following_stops_when_the_run_reaches_a_terminal_state(tmp_path, capsys):
    write_progress(tmp_path, ProgressState(run_id="r1", state="succeeded", message="done"))

    assert follow_run(tmp_path, "r1", timeout_seconds=5) == "succeeded"
    assert "done" in capsys.readouterr().out


def test_following_stops_when_the_run_is_cancelled(tmp_path, capsys):
    """The defect this closes: TERMINAL_STATES used to be a
    hand-written {"succeeded", "failed"}, so a cancelled run was never
    recognised as finished and `voxtrama run` waited for it forever.
    """
    write_progress(tmp_path, ProgressState(run_id="r1", state="cancelled", message="cancelled"))

    assert follow_run(tmp_path, "r1", timeout_seconds=5) == "cancelled"


def test_following_stops_when_the_run_is_interrupted(tmp_path, capsys):
    write_progress(tmp_path, ProgressState(run_id="r1", state="interrupted", message="lost"))

    assert follow_run(tmp_path, "r1", timeout_seconds=5) == "interrupted"


def test_following_a_run_that_never_publishes_gives_up(tmp_path):
    """Watching is not the run: giving up watching must not look like a failure."""
    assert follow_run(tmp_path, "missing", timeout_seconds=0.2) is None


def test_silence_is_bounded_but_a_long_run_is_not(tmp_path):
    """Two different waits, and conflating them hung the command.

    No worker publishing anything means nobody is executing the run, and
    that is worth giving up on quickly. A run that is running and takes an
    hour is not. So the bound is on the silence before the first state,
    never on the run itself.
    """
    assert follow_run(tmp_path, "nobody-listening", silence_seconds=0.1) is None
