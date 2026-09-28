"""Tests for voxtrama.engine.steps: turning depends_on into an order."""

from __future__ import annotations

import pytest

from voxtrama.engine.steps import resolve_order
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.errors import CyclicDependencyError, UnknownStepError


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _step(step_id: str, depends_on: list[str] | None = None) -> Step:
    return Step(
        id=step_id,
        skill=step_id,
        skill_version="1.0.0",
        depends_on=depends_on or [],
    )


def test_a_dependency_comes_before_the_step_that_declares_it() -> None:
    workflow = _workflow(_step("diarize", ["transcribe"]), _step("transcribe"))
    order = [step.id for step in resolve_order(workflow)]
    assert order.index("transcribe") < order.index("diarize")


def test_independent_steps_keep_the_order_of_the_file() -> None:
    """Two steps that depend on nothing must not be reordered between runs."""
    workflow = _workflow(_step("first"), _step("second"), _step("third"))
    assert [step.id for step in resolve_order(workflow)] == ["first", "second", "third"]


def test_every_step_appears_exactly_once() -> None:
    workflow = _workflow(
        _step("a"),
        _step("b", ["a"]),
        _step("c", ["a"]),
        _step("d", ["b", "c"]),
    )
    order = [step.id for step in resolve_order(workflow)]
    assert sorted(order) == ["a", "b", "c", "d"]
    assert order.index("d") == 3


def test_a_cycle_raises_before_anything_is_ordered() -> None:
    workflow = _workflow(_step("a", ["b"]), _step("b", ["a"]))
    with pytest.raises(CyclicDependencyError):
        resolve_order(workflow)


def test_a_step_depending_on_a_step_that_does_not_exist_raises() -> None:
    workflow = _workflow(_step("a", ["ghost"]))
    with pytest.raises(UnknownStepError):
        resolve_order(workflow)
