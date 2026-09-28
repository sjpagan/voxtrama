"""The file format of a generative skill: a Skill, plus its prompt.

This format follows one boundary: a skill declares what is
always true of a capability, and the prompt is the capability itself, not a
parameter of it. So it belongs on the skill, never on the workflow that
names one. SkillFile wraps Skill rather than extending it, because `Skill`
is what the manifest registers: giving it a `prompt` field that
means something only for one of its two model_class values would leak a
generative-only concept into the type every skill, extractive included,
is checked against.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from voxtrama.workflow.document import DocumentError, read_document
from voxtrama.workflow.skill import ModelClass, Skill


class SkillFileError(Exception):
    """A skill file failed to load: malformed YAML, a bad field, or the wrong model_class.

    Always names the file and the field: this message may be read after the
    file is gone, so its reader cannot go back and look.
    """


class SkillFile(BaseModel):
    """A generative skill as a file: the manifest's own Skill, plus the prompt it runs."""

    model_config = ConfigDict(extra="forbid")

    skill: Skill
    prompt: str


def load_skill_file(path: Path) -> SkillFile:
    """Parse and validate `path` as a SkillFile, rejecting anything but a generative skill.

    Only a generative skill may live in a file: an extractive one
    inspects the transcript rather than sampling a model, so it stays code.
    """
    try:
        skill_file = read_document(path, SkillFile)
    except DocumentError as exc:
        raise SkillFileError(str(exc)) from exc
    if skill_file.skill.model_class != ModelClass.GENERATIVE:
        raise SkillFileError(
            f"{path}: skill.model_class: must be 'generative', "
            f"got '{skill_file.skill.model_class}'. An extractive skill is code, not a file"
        )
    return skill_file
