"""Compose a custom workflow from skills that already exist.

A custom workflow is made in one of two ways, from scratch
(a name, a description, the steps chosen among the skills this
installation has) or by duplicating a system one and changing its steps.
Either way it only ever composes existing skills. Writing a new skill is
not part of this. Both ways end here, as the list of skills the person ticked.

The steps are laid out the same way every shipped workflow already is:
transcription first, speakers next when chosen, then every other step
reading the transcript with its speakers. A step that the source workflow
already declared keeps everything it declared (its alternatives above
all). A step added by the person gets the plain default.
"""

from __future__ import annotations

import re
import unicodedata

from voxtrama.workflow.definition import Step, Workflow

SCHEMA_VERSION = "v1"
FIRST_VERSION = "1.0.0"
TRANSCRIBE = "transcribe"
DIARIZE = "diarize"

# The order the shipped workflows run their skills in. A skill this list
# does not name goes after these, alphabetically.
_ORDER = (
    TRANSCRIBE,
    DIARIZE,
    "summarize",
    "extract_decisions",
    "extract_themes",
    "extract_concepts",
)


def ordered_skills(names: set[str] | list[str]) -> list[str]:
    """`names` in the order a workflow runs them."""
    known = [name for name in _ORDER if name in names]
    return known + sorted(set(names) - set(_ORDER))


def workflow_name_for(title: str) -> str:
    """The file's own identifier for `title`: lowercase, hyphenated, ASCII."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:60]


def _depends_on(skill: str, chosen: list[str]) -> list[str]:
    if skill == TRANSCRIBE:
        return []
    if skill == DIARIZE or DIARIZE not in chosen:
        return [TRANSCRIBE]
    return [DIARIZE]


def _step(skill: str, version: str, chosen: list[str], source: Workflow | None) -> Step:
    """The step for `skill`: the source's own, when it had one, re-wired to `chosen`."""
    kept = next((step for step in source.steps if step.skill == skill), None) if source else None
    depends_on = _depends_on(skill, chosen)
    if kept is not None:
        return kept.model_copy(update={"id": skill, "depends_on": depends_on})
    return Step(id=skill, skill=skill, skill_version=version, depends_on=depends_on)


def build_custom_workflow(
    title: str,
    description: str,
    skills: dict[str, str],
    source: Workflow | None = None,
    name: str | None = None,
    instructions: dict[str, str] | None = None,
) -> Workflow:
    """A workflow of `skills` (name to version), always starting with transcription.

    `name` keeps the identifier of a custom workflow being edited: renaming
    its title does not move its file, so runs that name it still find it.
    `instructions` is a step's own text in place of its skill's
    prompt, by skill name. A skill left out keeps its prompt.
    """
    chosen = ordered_skills({TRANSCRIBE, *skills})
    versions = {TRANSCRIBE: skills.get(TRANSCRIBE, FIRST_VERSION), **skills}
    return Workflow(
        name=name or workflow_name_for(title),
        title=title.strip(),
        version=FIRST_VERSION,
        schema_version=SCHEMA_VERSION,
        description=description.strip(),
        steps=[
            _step(skill, versions[skill], chosen, source).model_copy(
                update={"instructions": (instructions or {}).get(skill)}
            )
            for skill in chosen
        ],
    )
