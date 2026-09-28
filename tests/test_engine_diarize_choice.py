"""Unit tests for engine.diarize_choice: the diarize opt-out.

Split out the same way tests/test_engine_choice_check_step_skills.py is
split from tests/test_engine_choice_check.py: one file per rule family, so
neither grows past the project's own line limit.
"""

from __future__ import annotations

from voxtrama.engine.diarize_choice import check_diarize_choice, drop_declined_diarize
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow


def _workflow(steps: list[Step]) -> Workflow:
    return Workflow(
        name="wf", version="1.0.0", schema_version="v1", description="test fixture", steps=steps
    )


def test_skipping_diarize_is_accepted_when_nothing_depends_on_it():
    steps = [
        Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
        Step(id="diarize", skill="diarize", skill_version="1.0.0", depends_on=["transcribe"]),
    ]
    assert check_diarize_choice(RunChoices(diarize=False), _workflow(steps)) == []


def test_skipping_diarize_is_rejected_when_another_step_depends_on_it():
    steps = [
        Step(id="diarize", skill="diarize", skill_version="1.0.0"),
        Step(id="extract", skill="extract", skill_version="1.0.0", depends_on=["diarize"]),
    ]
    rejections = check_diarize_choice(RunChoices(diarize=False), _workflow(steps))
    assert len(rejections) == 1
    assert rejections[0].field == "diarize"
    assert rejections[0].declared_by == "step extract"


def test_choosing_not_to_skip_or_choosing_nothing_never_rejects():
    steps = [
        Step(id="diarize", skill="diarize", skill_version="1.0.0"),
        Step(id="extract", skill="extract", skill_version="1.0.0", depends_on=["diarize"]),
    ]
    assert check_diarize_choice(RunChoices(), _workflow(steps)) == []
    assert check_diarize_choice(RunChoices(diarize=True), _workflow(steps)) == []


def test_dropping_declined_diarize_removes_only_that_step():
    ordered = [
        Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
        Step(id="diarize", skill="diarize", skill_version="1.0.0", depends_on=["transcribe"]),
    ]
    dropped = drop_declined_diarize(ordered, RunChoices(diarize=False))
    assert [step.id for step in dropped] == ["transcribe"]


def test_dropping_is_a_no_op_when_the_run_did_not_decline():
    ordered = [Step(id="diarize", skill="diarize", skill_version="1.0.0")]
    assert drop_declined_diarize(ordered, RunChoices()) == ordered
