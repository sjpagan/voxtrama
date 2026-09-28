"""step_progress: a plain count, not a live percentage."""

from __future__ import annotations

from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.step_progress import step_progress


def _step(state: StepState, position: int) -> RunStep:
    return RunStep(
        run_id="run-1",
        step_id=f"step-{position}",
        skill="transcribe",
        skill_version="1",
        position=position,
        state=state,
    )


def test_a_run_with_no_steps_yet_has_no_progress_to_report() -> None:
    assert step_progress([]) == (0, 0)


def test_the_current_number_points_at_the_step_now_running() -> None:
    """succeeded, succeeded, running, pending, pending -> 3 of 5."""
    steps = [
        _step(StepState.SUCCEEDED, 0),
        _step(StepState.SUCCEEDED, 1),
        _step(StepState.RUNNING, 2),
        _step(StepState.PENDING, 3),
        _step(StepState.PENDING, 4),
    ]

    assert step_progress(steps) == (3, 5)


def test_a_failed_step_counts_as_terminal_like_a_succeeded_one() -> None:
    steps = [
        _step(StepState.SUCCEEDED, 0),
        _step(StepState.FAILED, 1),
        _step(StepState.PENDING, 2),
    ]

    assert step_progress(steps) == (3, 3)


def test_a_run_still_entirely_pending_is_on_its_first_step() -> None:
    steps = [_step(StepState.PENDING, 0), _step(StepState.PENDING, 1)]

    assert step_progress(steps) == (1, 2)


def test_a_finished_run_never_reads_higher_than_its_own_total() -> None:
    steps = [_step(StepState.SUCCEEDED, 0), _step(StepState.SKIPPED, 1)]

    assert step_progress(steps) == (2, 2)
