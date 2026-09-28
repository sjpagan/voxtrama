"""What a workflow produces, read off its steps.

Split out of workflow_offers.py to keep that file under the project's line
limit. This is one self-contained answer (`produces`), plus one small
formatting rule (`default_title`) that had nowhere else to live once the
split was needed.

`_PRODUCES_BY_SKILL` names, once, which kind each skill this package ships
contributes. These are the `kind` identifiers components/run_output.html's
`output_kind_label` already translates, reused instead of a second set of
English strings for the same four nouns plus the two structural ones
(transcript, speakers) a workflow with no generative step still produces.
A skill this dict does not name yet (one that ships after this file was
last touched) contributes nothing instead of guessing.
"""

from __future__ import annotations

from voxtrama.workflow.definition import Workflow

_PRODUCES_BY_SKILL: dict[str, str] = {
    "transcribe": "transcript",
    "diarize": "speakers",
    "summarize": "key_point",
    "extract_decisions": "decision",
    "extract_concepts": "concept",
    "extract_themes": "theme",
}


def produces(workflow: Workflow) -> list[str]:
    """Every kind `workflow`'s steps contribute, in step order, each named once."""
    kinds = (
        _PRODUCES_BY_SKILL[step.skill]
        for step in workflow.steps
        if step.skill in _PRODUCES_BY_SKILL
    )
    return list(dict.fromkeys(kinds))


def default_title(name: str) -> str:
    """ "meeting-decisions" -> "Meeting decisions": only ever reached for a Workflow
    whose `title` is None (workflow.definition.Workflow's docstring says why
    that can happen)."""
    return name.replace("-", " ").replace("_", " ").capitalize()
