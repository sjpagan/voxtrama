"""What GET /workflows shows: the workflow cards,
the card that creates a custom workflow, and the detail of one workflow.

Reuses rendering.workflow_offers.build_offer for what a workflow
produces and which alternatives a step declares: the same StepChoices
the engine already computes, not a second "what is compatible" answer
invented for this page. This module adds what that one never needed:
whether a workflow is a system or a custom one, the skills its card lists
(the workflow's own, never the same chips on every card), and every step
in the file's order.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.rendering.skill_instructions import StepInstructions, step_instructions
from voxtrama.rendering.workflow_offers import StepChoiceRow, WorkflowOffer
from voxtrama.workflow.definition import Workflow


@dataclass(frozen=True)
class WorkflowStepView:
    """One step of a workflow, as the detail numbers it: the skill says what it does."""

    step_id: str
    skill: str
    skill_version: str
    # What the step tells the model, None for a built-in with no prompt.
    instructions: StepInstructions | None = None


@dataclass(frozen=True)
class WorkflowCard:
    """One workflow's card: its offer, whether it ships with Voxtrama, and its skills."""

    offer: WorkflowOffer
    system: bool
    skills: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowDetail:
    """The detail under the grid: every step in order, and the Advanced
    section's editable alternatives."""

    card: WorkflowCard
    steps: list[WorkflowStepView]
    editable_steps: list[StepChoiceRow]


@dataclass(frozen=True)
class CustomSlots:
    """How many custom workflows the edition allows, and how many exist."""

    allowed: int
    used: int

    @property
    def free(self) -> int:
        return max(0, self.allowed - self.used)


def workflow_card(workflow: Workflow, offer: WorkflowOffer, system: bool) -> WorkflowCard:
    skills = tuple(dict.fromkeys(step.skill for step in workflow.steps))
    return WorkflowCard(offer=offer, system=system, skills=skills)


def workflow_steps(workflow: Workflow) -> list[WorkflowStepView]:
    """Every step of `workflow`, in its declared order."""
    return [
        WorkflowStepView(step.id, step.skill, step.skill_version, step_instructions(step))
        for step in workflow.steps
    ]


def workflow_detail(workflow: Workflow, offer: WorkflowOffer, system: bool) -> WorkflowDetail:
    return WorkflowDetail(
        card=workflow_card(workflow, offer, system),
        steps=workflow_steps(workflow),
        editable_steps=offer.step_choices,
    )
