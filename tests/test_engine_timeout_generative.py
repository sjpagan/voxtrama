"""A long recap is budgeted in the job, not killed by the queue half-way."""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.engine.timeout_generative import generative_allowance, windows_for
from voxtrama.workflow.definition import Step, Workflow


def _workflow(*skills: str) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id=s, skill=s, skill_version="1.0.0") for s in skills],
    )


def test_a_workflow_without_generative_steps_adds_nothing() -> None:
    settings = Settings(provider_timeout_seconds=1800, parallel_windows=2)

    assert generative_allowance(_workflow("transcribe", "diarize"), 3600, settings) == 0
    assert generative_allowance(None, 3600, settings) == 0


def test_every_generative_step_gets_its_windows_ceilings() -> None:
    settings = Settings(provider_timeout_seconds=100, parallel_windows=2)
    workflow = _workflow("transcribe", "summarize", "extract_decisions")
    rounds = -(-windows_for(3278) // 2)  # the 54:38 recording that ran out

    assert windows_for(3278) >= 4
    assert generative_allowance(workflow, 3278, settings) == 2 * rounds * 100


def test_a_short_recording_is_still_one_window() -> None:
    assert windows_for(30) == 1
