"""Workflow and Step: the declarative composition of skills (core).

Only the shape of sequencing, dependencies, branches, retries, fallbacks
and what a run may choose lives here. No execution.
Workflow is generated into schemas/workflow-v1.json by
scripts/generate_workflow_schemas.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from voxtrama.workflow.skill import Privacy


class RetryPolicy(BaseModel):
    """How many times a failed step is retried before falling back or failing."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=0, ge=0)


class OnError(BaseModel):
    """A step's behaviour on failure: retry, then an optional fallback step."""

    model_config = ConfigDict(extra="forbid")

    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    fallback_step: str | None = None


class SkillRef(BaseModel):
    """A skill named the way a Step already names one: name plus version."""

    model_config = ConfigDict(extra="forbid")

    skill: str
    skill_version: str


class StepAllows(BaseModel):
    """What a run may choose for this step. Empty means: nothing, here.

    An empty list is the restrictive default, not "anything goes": "the
    tighter constraint wins" extends to the run itself, so a step that
    declares nothing here offers no choice to widen.
    """

    model_config = ConfigDict(extra="forbid")

    skills: list[SkillRef] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)


class Step(BaseModel):
    """One step of a Workflow: a Skill, its dependencies, and its failure handling."""

    model_config = ConfigDict(extra="forbid")

    id: str
    skill: str
    skill_version: str
    depends_on: list[str] = Field(default_factory=list)
    condition: str | None = None
    on_error: OnError = Field(default_factory=OnError)
    # Replaces the former model_override: dict[str, Any].
    # "override" names who bypasses a constraint, while what this field
    # holds is what is *permitted*, and dict[str, Any] let a typo in a
    # workflow file pass through silently, saying nothing.
    allows: StepAllows = Field(default_factory=StepAllows)
    # `local_only` keeps this step's content on the machine even when
    # its skill says `any`. It only ever narrows (workflow.privacy).
    privacy: Privacy | None = None
    # A custom workflow's own instructions for a generative step, in place
    # of its skill's prompt. The skill itself never changes (workflow.instructions).
    instructions: str | None = None


class Workflow(BaseModel):
    """A named, versioned composition of Skills.

    See docs/guide/workflow-files.md for how to write one: this docstring
    becomes this schema's own "description", so the pointer survives
    scripts/generate_workflow_schemas.py regenerating workflow-v1.json.

    `title` is `name` read by a person, not by the CLI or POST
    /recordings/{id}/runs: both of those still take `name`, which stays
    the file's own identifier, lowercase and hyphenated, forever. Optional
    here, at the schema's own level, rather than required: the dozens of
    throwaway Workflow objects the engine's own test suite builds to
    exercise dependency graphs, retries and conditions have no page to be
    readable on, and forcing every one of them to invent a title would be
    a cost paid by code no page ever shows. The actual requirement
    (every workflow the package ships declares one) is enforced
    instead where it means something: tests/test_workflows_reach_every_
    skill.py's own coverage of workflows/*.yaml. rendering.workflow_offers.
    build_offer falls back to a formatted `name` for the rare Workflow
    that reaches it without one.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    title: str | None = None
    version: str
    # The only shape this version reads. Until 1.0 nothing older or newer is
    # promised: a file written for another one is refused, not guessed at.
    schema_version: Literal["v1"]
    description: str
    # `local_only` here holds for every step (workflow.privacy).
    privacy: Privacy = Privacy.ANY
    steps: list[Step]
