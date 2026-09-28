"""Find a generative skill's file by name, across the two places skill files live.

Mirrors engine.catalog exactly, one level down: the ones we ship
are files of the package, read-only, and the ones a user writes live in the
data directory. The user's root wins when both hold the same name, as a
user's workflow wins over ours: someone can try a modified copy without
our file getting in the way, and neither file ever writes the other. This
module makes no second decision.

The bottom half turns a name into a registry entry without raising.
load_generative_skills keeps a broken file's error instead of letting it
propagate, and generative_registry turns that into a StepFunction that
fails with it when a run names it, not at import.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from voxtrama.engine.context import ExecutionContext, StepFunction
from voxtrama.engine.generative import run_generative
from voxtrama.workflow.document import DocumentNotFoundError, find_document
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill_file import SkillFile, SkillFileError, load_skill_file


class SkillFileNotFoundError(FileNotFoundError):
    """No skill file named `name` in any of the roots we look in."""


def find_skill_file(name: str) -> Path:
    """The file declaring the generative skill called `name`."""
    try:
        return find_document("skills", name, "skill file")
    except DocumentNotFoundError as exc:
        raise SkillFileNotFoundError(str(exc)) from exc


def load_named_skill_file(name: str) -> SkillFile:
    """Load and validate the generative skill file called `name`."""
    return load_skill_file(find_skill_file(name))


@dataclass(frozen=True)
class LoadedSkill:
    """`name` loaded into `skill_file`, or failed to, with `error` saying why.

    Exactly one of skill_file and error is set. Kept as data instead of
    raising, so the caller (engine.builtin) decides what "a skill that did
    not load" means for the registry, instead of this module deciding it
    by crashing whoever imports it.
    """

    name: str
    skill_file: SkillFile | None
    error: str | None


# The generative skills the package ships. A list, not discovery by
# directory listing: a name here is a promise the registry keeps, and a file
# appearing in a root should not silently become a skill the engine offers.
GENERATIVE_SKILL_NAMES = [
    "summarize",
    "extract_decisions",
    "extract_concepts",
    "extract_themes",
]


def load_generative_skills(names: list[str]) -> list[LoadedSkill]:
    """Load each of `names`, one skill file per name, never raising.

    A broken skill file must never stop the product from starting: `doctor`
    is there to diagnose a bad configuration, and a crash at import time
    takes that tool down with everything else. The error a
    broken file raised is kept verbatim (path and field, or the YAML
    parser's message) for the caller to surface later, when the skill is
    named.
    """
    loaded = []
    for name in names:
        try:
            loaded.append(LoadedSkill(name, load_named_skill_file(name), None))
        except (SkillFileError, SkillFileNotFoundError) as exc:
            loaded.append(LoadedSkill(name, None, str(exc)))
    return loaded


def broken_step(loaded: LoadedSkill) -> StepFunction:
    """A step that raises loaded.error when a run calls it.

    Stands in for the step a working skill would have registered, so a
    workflow naming it fails saying which file and which field (instead of
    "unknown skill"), and only when it runs, never at import.
    """

    def _run(ctx: ExecutionContext) -> dict[str, Any]:
        raise SkillFileError(f"{loaded.name}: {loaded.error}")

    return _run


def generative_registry(loaded: list[LoadedSkill]) -> tuple[dict[str, StepFunction], SkillRegistry]:
    """Turn what load_generative_skills found into a StepFunction and a Skill registry.

    A skill that failed to load still gets a step (broken_step above) but
    no Skill declaration: nothing here could invent one for a file that
    never parsed.
    """
    steps: dict[str, StepFunction] = {}
    skills: SkillRegistry = {}
    for entry in loaded:
        if entry.skill_file is None:
            steps[entry.name] = broken_step(entry)
            continue
        steps[entry.name] = partial(run_generative, entry.skill_file)
        skills[entry.name] = {entry.skill_file.skill.version: entry.skill_file.skill}
    return steps, skills


def builtin_generative_registry() -> tuple[dict[str, StepFunction], SkillRegistry]:
    """The steps and skills for every generative skill the package ships.

    One call instead of two: engine.builtin has no need to know that
    loading and registering are separate stages. Keeping the pair here
    lets that module stay a registry and not a loader.
    """
    return generative_registry(load_generative_skills(GENERATIVE_SKILL_NAMES))
