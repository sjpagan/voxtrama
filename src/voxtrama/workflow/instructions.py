"""A custom workflow's own instructions for a generative step.

The system skills are read, never changed: their prompt is what the
Workflows page shows. A custom workflow can start from that text and
change it for one of its steps. The text is kept on the step
(`Step.instructions`), the skill file stays as shipped, and the step's
output still has to fit the skill's own output_schema.

The text is a template: {transcript} is where the transcript goes, and
{language} and {detail} are filled in too. A literal brace is written
twice, {{ or }}.
"""

from __future__ import annotations

from string import Formatter

from voxtrama.workflow.definition import Step, Workflow

PLACEHOLDERS = ("transcript", "language", "detail")


class InstructionsError(ValueError):
    """Instructions a step cannot run with. The message says why."""


def check_instructions(text: str) -> None:
    """Raise InstructionsError unless `text` is a template a step can fill.

    Each field must be one of PLACEHOLDERS, bare: no `{transcript.upper}`,
    no `{transcript:>999999999}`, which made check_instructions itself
    build a string of a gigabyte.
    """
    if "{transcript}" not in text:
        raise InstructionsError("the instructions must say where the transcript goes: {transcript}")
    try:
        fields = [part[1:] for part in Formatter().parse(text) if part[1] is not None]
    except ValueError as exc:
        raise InstructionsError(f"{exc}; write a literal brace twice") from exc
    for name, spec, conversion in fields:
        if name not in PLACEHOLDERS or spec or conversion:
            raise InstructionsError(
                f"unknown placeholder {{{name}}}; use {{transcript}}, {{language}}, {{detail}},"
                " and write a literal brace twice"
            )


def step_instructions(workflow: Workflow, ordered: list[Step]) -> dict[str, str]:
    """Step id -> its own instructions, where the step still runs the skill they were for."""
    declared = {step.id: step for step in workflow.steps}
    return {
        step.id: step.instructions
        for step in ordered
        if step.instructions and step.skill == declared[step.id].skill
    }
