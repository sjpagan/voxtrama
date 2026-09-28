"""Unit tests for rendering.workflow_offers: build_offer/failed_offer.

Builds WorkflowChoices fixtures directly, the same way test_workflow_choices_calc.py
builds Workflow/Skill ones: no route, no HTTP client, just the one translation this
module is responsible for: an already-computed WorkflowChoices into a WorkflowOffer.
"""

from __future__ import annotations

from voxtrama.api.workflow_choices import StepChoices, WorkflowChoices, WorkflowRef
from voxtrama.rendering.workflow_offers import SkillOption, build_offer, failed_offer
from voxtrama.workflow.definition import SkillRef, Step, Workflow


def _workflow(steps: list[Step]) -> Workflow:
    return Workflow(
        name="wf", version="1.0.0", schema_version="v1", description="Test fixture.", steps=steps
    )


def _choices(**overrides: object) -> WorkflowChoices:
    defaults: dict[str, object] = {
        "workflow": WorkflowRef(name="wf", version="1.0.0"),
        "hardware_profiles": ["low", "base", "high"],
        "generative_models": None,
        "steps": [],
    }
    defaults.update(overrides)
    return WorkflowChoices(**defaults)


def test_a_workflow_with_every_profile_offered_is_available() -> None:
    offer = build_offer(_workflow([]), _choices(), "base", None)

    assert offer.available
    assert offer.unavailable_reason is None
    assert offer.hardware_profiles == ["low", "base", "high"]
    assert offer.hardware_profile_default == "base"


def test_a_workflow_with_no_hardware_profile_offered_is_unavailable_with_a_reason() -> None:
    """An empty option set is shown, not hidden, the same rule
    engine.choice_check's own coherence with this route already relies on for the
    non-empty case (tests/test_workflow_choices_calc.py).
    """
    offer = build_offer(_workflow([]), _choices(hardware_profiles=[]), "base", None)

    assert not offer.available
    assert offer.unavailable_reason is not None


def test_generative_model_default_is_carried_through_when_the_installation_has_one() -> None:
    step = StepChoices(
        step_id="a", skill="s", skill_version="1.0.0", skills=[], models=["m1", "m2"]
    )
    offer = build_offer(
        _workflow([Step(id="a", skill="s", skill_version="1.0.0")]),
        _choices(generative_models=["m1", "m2"], steps=[step]),
        "base",
        "qwen3:30b",
    )

    assert offer.generative_models == ["m1", "m2"]
    assert offer.generative_model_default == "qwen3:30b"


def test_a_step_with_alternatives_carries_its_own_default_label() -> None:
    step = StepChoices(
        step_id="extract",
        skill="extract_decisions",
        skill_version="1.0.0",
        skills=[SkillRef(skill="extract_themes", skill_version="1.0.0")],
        models=[],
    )
    offer = build_offer(
        _workflow([Step(id="extract", skill="extract_decisions", skill_version="1.0.0")]),
        _choices(steps=[step]),
        "base",
        None,
    )

    assert len(offer.step_choices) == 1
    row = offer.step_choices[0]
    assert row.default_label == "extract_decisions 1.0.0"
    assert row.options == [SkillOption(value="extract_themes:1.0.0", label="extract_themes 1.0.0")]


def test_a_step_with_no_alternatives_is_left_out_of_step_choices() -> None:
    step = StepChoices(step_id="a", skill="s", skill_version="1.0.0", skills=[], models=[])
    offer = build_offer(
        _workflow([Step(id="a", skill="s", skill_version="1.0.0")]),
        _choices(steps=[step]),
        "base",
        None,
    )

    assert offer.step_choices == []


def test_a_workflow_with_a_title_carries_it_through() -> None:
    workflow = Workflow(
        name="wf",
        title="Meeting decisions",
        version="1.0.0",
        schema_version="v1",
        description="Test fixture.",
        steps=[],
    )

    offer = build_offer(workflow, _choices(), "base", None)

    assert offer.title == "Meeting decisions"


def test_a_workflow_with_no_title_falls_back_to_its_own_name_formatted() -> None:
    offer = build_offer(_workflow([]), _choices(), "base", None)

    assert offer.title == "Wf"


def test_produces_is_read_off_the_steps_not_hand_written() -> None:
    steps = [
        Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
        Step(id="diarize", skill="diarize", skill_version="1.0.0"),
        Step(id="extract", skill="extract_decisions", skill_version="1.0.0"),
    ]
    offer = build_offer(_workflow(steps), _choices(), "base", None)

    assert offer.produces == ["transcript", "speakers", "decision"]


def test_produces_names_each_kind_once_even_when_a_skill_repeats() -> None:
    steps = [
        Step(id="a", skill="extract_decisions", skill_version="1.0.0"),
        Step(id="b", skill="extract_decisions", skill_version="1.0.0"),
    ]
    offer = build_offer(_workflow(steps), _choices(), "base", None)

    assert offer.produces == ["decision"]


def test_failed_offer_is_unavailable_and_names_no_workflow_content() -> None:
    offer = failed_offer("broken-workflow", "steps[0].skill: unknown skill 'x' version '1'")

    assert offer.name == "broken-workflow"
    assert not offer.available
    assert "unknown skill" in offer.unavailable_reason
    assert offer.description == ""
    assert offer.step_choices == []
