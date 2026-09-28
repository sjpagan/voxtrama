"""What the custom-workflow form shows: its fields, and every skill to pick.

`skills` is every skill this installation has, in the order a workflow
runs them (workflow.custom_build.ordered_skills), each ticked when the
workflow the form starts from uses it. Transcription is always ticked
and cannot be removed: every other step reads the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.rendering.skill_instructions import system_prompt
from voxtrama.workflow.custom_build import TRANSCRIBE, ordered_skills
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.loader import SkillRegistry


@dataclass(frozen=True)
class SkillPick:
    name: str
    version: str
    checked: bool
    required: bool
    # The text the step sends to the model, to start editing from.
    # The workflow's own when it has one, else the skill's. None for a
    # built-in that sends nothing.
    instructions: str | None = None
    edited: bool = False

    @property
    def value(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True)
class CustomForm:
    title: str
    description: str
    source: str | None
    original: str | None
    skills: tuple[SkillPick, ...]


def custom_form(workflow: Workflow | None, skills: SkillRegistry, editing: bool) -> CustomForm:
    """The form, empty or filled from `workflow` (a copy of it, or its own edit)."""
    used = {step.skill for step in workflow.steps} if workflow else {TRANSCRIBE}
    own = {s.skill: s.instructions for s in workflow.steps if s.instructions} if workflow else {}
    picks = tuple(
        SkillPick(
            name=name,
            version=max(skills[name]),
            checked=name in used or name == TRANSCRIBE,
            required=name == TRANSCRIBE,
            instructions=own.get(name) or system_prompt(name),
            edited=name in own,
        )
        for name in ordered_skills(set(skills))
    )
    if workflow is None:
        return CustomForm("", "", None, None, picks)
    title = workflow.title or workflow.name
    return CustomForm(
        title=title if editing else f"{title} (copy)",
        description=workflow.description,
        source=None if editing else workflow.name,
        original=workflow.name if editing else None,
        skills=picks,
    )
