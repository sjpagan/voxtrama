"""Find a workflow by name, across the two places workflows live.

They live in two roots: the ones we ship are files of the package,
read-only, and the ones a user writes or duplicates live in the data
directory. The user's root wins when both hold the same name, so someone can
try a modified copy without our file getting in the way, and neither file
ever writes the other.

Only lookup lives here. Deactivation, catalogue states and the update notice
belong to the admin page, and the engine must not learn
about a user's display preferences: a workflow hidden from a list still runs
when it is named.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.skill_catalog import GENERATIVE_SKILL_NAMES, load_generative_skills
from voxtrama.workflow.custom_limit import refused_custom_workflows
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.document import DocumentNotFoundError, document_roots, find_document
from voxtrama.workflow.loader import SkillNotFoundError, load_workflow


class WorkflowNotFoundError(FileNotFoundError):
    """No workflow with that name in any of the roots we look in."""


def list_workflow_names() -> list[str]:
    """Every workflow name found across both roots, alphabetically.

    Not the full catalogue: that also carries origin,
    the current/previous/archived state and the admin page's
    deactivation preference, none of it built yet. This only says
    which names exist, for a caller (the workflow-choice panel)
    that has to offer every one of them instead of resolving one it
    already knows. Each name still goes through load_named_workflow to
    become a Workflow, the one place user-root-wins and validation
    against the skill registry happen.
    """
    names: set[str] = set()
    for root in document_roots("workflows"):
        try:
            names.update(path.stem for path in root.glob("*.yaml"))
        except OSError:
            continue
    return sorted(names - refused_custom_workflows())


def find_workflow_file(name: str) -> Path:
    """The file declaring the workflow called `name`, if the edition allows it."""
    if name in refused_custom_workflows():
        raise WorkflowNotFoundError(f"workflow '{name}' is beyond the edition's custom limit")
    try:
        return find_document("workflows", name, "workflow")
    except DocumentNotFoundError as exc:
        raise WorkflowNotFoundError(str(exc)) from exc


def _broken_skill_errors() -> dict[str, str]:
    """Every generative skill the package ships that failed to load, and why.

    Read on the error path only (load_named_workflow calls it once a
    workflow has already been rejected), so re-reading those files costs
    something only when someone needs to be told what is wrong, and
    nothing on a run that is going fine.
    """
    return {
        loaded.name: loaded.error
        for loaded in load_generative_skills(GENERATIVE_SKILL_NAMES)
        if loaded.error is not None
    }


def load_named_workflow(name: str) -> Workflow:
    """Load and validate the workflow called `name` against the built-in skills.

    A skill whose file did not load is absent from the registry, so the
    validator can only call it unknown. That is true of the registry and
    false of the world: the skill is there, its file is broken. Someone
    reading "unknown skill 'summarize'" looks for a typo in the name
    instead of a comma in their YAML, an error that lies about its cause.
    So the real reason is looked up and reported, once the workflow has
    already been rejected.
    """
    try:
        return load_workflow(find_workflow_file(name), BUILTIN_SKILLS)
    except SkillNotFoundError as exc:
        broken = _broken_skill_errors()
        named = [f"'{skill}' ({reason})" for skill, reason in broken.items() if skill in str(exc)]
        if not named:
            raise
        raise SkillNotFoundError(
            f"{exc}; that skill has a file that did not load: {'; '.join(named)}"
        ) from exc
