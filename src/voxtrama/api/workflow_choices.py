"""Pydantic response models for GET /workflows/{name}/choices.

Lives in api/, not api/routes/: rendering.workflow_offers imports
WorkflowChoices from here, and api/routes/__init__.py imports every router
eagerly, so reaching into that package for a response model with no route
of its own turned rendering's deliberate dependency on this type into a
real import cycle the first time voxtrama.rendering was imported on its
own. routes/workflow_choices.py keeps the router and the arithmetic that
builds these. This module only carries the shapes both sides agree on.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from voxtrama.workflow.definition import SkillRef


class WorkflowRef(BaseModel):
    """The workflow this response is about: enough to tell it apart, no more."""

    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class StepChoices(BaseModel):
    """One step's declared skill and what, if anything, a run may choose for it."""

    model_config = ConfigDict(extra="forbid")
    step_id: str
    skill: str
    skill_version: str
    skills: list[SkillRef]
    models: list[str]


class WorkflowChoices(BaseModel):
    """What GET /workflows/{name}/choices answers: nothing the client must derive itself."""

    model_config = ConfigDict(extra="forbid")
    workflow: WorkflowRef
    hardware_profiles: list[str]
    generative_models: list[str] | None
    steps: list[StepChoices]
