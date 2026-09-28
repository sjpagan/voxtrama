"""Tests for rendering.run_page.run_page_view.

Builds Run/RunStep rows directly, unsaved: this presenter only reads
attributes already on the rows a route has fetched, never a session, so
there is nothing here for a database to add.
"""

from __future__ import annotations

from datetime import UTC, datetime
from gettext import NullTranslations

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.run_page import run_page_view

_translator = Translator(locale="en", translations=NullTranslations())


def _run(state: RunState) -> Run:
    return Run(
        id="run-1",
        workflow_name="demo",
        workflow_version="1.0.0",
        state=state,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _step(step_id: str, position: int, state: StepState) -> RunStep:
    return RunStep(
        run_id="run-1",
        step_id=step_id,
        skill="transcribe",
        skill_version="1",
        position=position,
        state=state,
    )


def test_steps_are_ordered_by_position_regardless_of_row_order() -> None:
    steps = [_step("b", 1, StepState.PENDING), _step("a", 0, StepState.RUNNING)]

    view = run_page_view(_run(RunState.RUNNING), steps, _translator)

    assert [row.step_id for row in view.steps] == ["a", "b"]


def test_an_interrupted_run_still_shows_the_step_it_never_reached() -> None:
    """engine.progress.record_planned_steps writes every step `pending` up
    front: a run interrupted after its first step must not look one step
    shorter than the workflow is.
    """
    steps = [_step("transcribe", 0, StepState.SUCCEEDED), _step("summarize", 1, StepState.PENDING)]

    view = run_page_view(_run(RunState.INTERRUPTED), steps, _translator)

    assert [row.state for row in view.steps] == ["succeeded", "pending"]
    assert view.is_final is True


def test_a_running_steps_tone_is_warning_and_a_pending_ones_is_none() -> None:
    steps = [_step("transcribe", 0, StepState.RUNNING), _step("summarize", 1, StepState.PENDING)]

    view = run_page_view(_run(RunState.RUNNING), steps, _translator)

    assert view.steps[0].tone == "warning"
    assert view.steps[1].tone is None


def test_a_running_run_is_not_final() -> None:
    view = run_page_view(_run(RunState.RUNNING), [], _translator)

    assert view.is_final is False
    assert view.state_tone == "warning"


def test_a_succeeded_run_is_final_with_a_success_tone() -> None:
    view = run_page_view(_run(RunState.SUCCEEDED), [], _translator)

    assert view.is_final is True
    assert view.state_tone == "success"


def test_the_runs_name_is_the_recordings_filename_when_there_is_one() -> None:
    """A person recognises the file, never the workflow's own YAML name."""
    view = run_page_view(_run(RunState.RUNNING), [], _translator, "Team retro, 24 Sep.m4a")

    assert view.name == "Team retro, 24 Sep.m4a"
    assert view.workflow_name == "demo"


def test_the_runs_name_falls_back_to_the_workflow_when_there_is_no_recording() -> None:
    """No other source is tried: a run whose import failed before one existed."""
    view = run_page_view(_run(RunState.RUNNING), [], _translator, None)

    assert view.name == "demo"


def test_a_steps_label_reads_its_own_step_id_not_its_skill() -> None:
    steps = [_step("extract_decisions", 0, StepState.PENDING)]

    view = run_page_view(_run(RunState.RUNNING), steps, _translator)

    assert view.steps[0].label == "Extract Decisions"
    assert view.steps[0].skill == "transcribe"


def test_the_step_progress_is_the_step_now_running_out_of_the_total() -> None:
    steps = [
        _step("transcribe", 0, StepState.SUCCEEDED),
        _step("speakers", 1, StepState.RUNNING),
        _step("extract", 2, StepState.PENDING),
    ]

    view = run_page_view(_run(RunState.RUNNING), steps, _translator)

    assert view.step_progress_current == 2
    assert view.step_progress_total == 3


def test_step_states_and_run_states_list_every_value_for_the_label_catalog() -> None:
    """components/run_labels.html's label_catalog() needs every state a
    RunStep or a Run can be in, not only the ones this particular run
    happens to show. A review caught run_page.js carrying its
    own English labels instead of reading a translated catalogue.
    """
    view = run_page_view(_run(RunState.RUNNING), [], _translator)

    assert view.step_states == ["pending", "running", "succeeded", "failed", "skipped"]
    assert view.run_states == [
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
    ]


def test_a_job_with_a_name_is_titled_by_it_not_by_its_file() -> None:
    """The job's own name comes first; the file is what it fell back to."""
    run = _run(RunState.RUNNING)
    run.label = "Weekly product sync"

    view = run_page_view(run, [], _translator, "Weekly product sync.flac")

    assert view.name == "Weekly product sync"
