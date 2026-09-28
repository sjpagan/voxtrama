"""The line a step with no loop to measure prints.

Split from test_cli_progress for the file-length limit, the same way
test_cli_follow_run was: those tests cover an activity the engine
measured, these cover the case where there is nothing to measure and only
the declared ceiling to show.
"""

from datetime import UTC, datetime, timedelta

from voxtrama.cli.progress_view import ProgressPrinter
from voxtrama.engine.progress_file import ProgressState


def test_a_declared_ceiling_shows_elapsed_only_when_interactive(capsys):
    """A generative step has no loop to measure a position from:
    only its declared timeout, and the elapsed a person can compute
    themselves. The engine never publishes elapsed on its own.
    """
    started = (datetime.now(UTC) - timedelta(seconds=40)).isoformat()
    state = ProgressState(
        run_id="r1",
        state="running",
        step_total=3,
        step_index=1,
        message="running summarize",
        ceiling_seconds=120,
        updated_at=started,
    )

    ProgressPrinter(interactive=True).render(state)
    interactive_out = capsys.readouterr().out
    assert "elapsed of 120s" in interactive_out
    assert "40s" in interactive_out or "41s" in interactive_out
    # Four of the skills on disk are generative: the line has to say which
    # step is waiting, not just that some model was asked.
    assert "[2/3] running summarize" in interactive_out

    ProgressPrinter(interactive=False).render(state)
    assert (
        capsys.readouterr().out.strip() == "[2/3] running summarize: asking the model, up to 120s"
    )


def test_an_unreadable_timestamp_does_not_kill_the_watcher(capsys):
    """A progress file whose updated_at cannot be parsed still renders.

    read_progress only refuses a payload ProgressState cannot be built
    from, and any string builds: the value is only parsed here, while
    someone is watching a run that is going fine.
    """
    state = ProgressState(
        run_id="r1", state="running", ceiling_seconds=120, updated_at="not-a-timestamp"
    )

    ProgressPrinter(interactive=True).render(state)

    assert "asking the model, up to 120s" in capsys.readouterr().out


def test_a_declared_ceiling_prints_once_in_a_log(capsys):
    """Elapsed would change every second. In a log that would be a line a
    second for the whole wait, which is the noise left
    to the reader to avoid, not the engine to throttle.
    """
    printer = ProgressPrinter(interactive=False)
    state = ProgressState(run_id="r1", state="running", ceiling_seconds=120)

    printer.render(state)
    printer.render(state)

    assert capsys.readouterr().out.count("asking the model") == 1
