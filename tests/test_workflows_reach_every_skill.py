"""Every registered generative skill must be reachable from a workflow.

The defect this file exists to prevent: `summarize` was registered in the
engine (`engine.skill_catalog.GENERATIVE_SKILL_NAMES` listed it, the file
`skills/summarize.yaml` existed, its tests passed) and **none of the four
workflows named it among their steps**. Runnable code, covered by tests,
that no run could reach: the user never saw a summary.

It asserts the invariant, not the mechanism: not «summarize is in workflow
X», but «no registered skill stays unreachable». A new skill that no
workflow names turns this test red, which is the moment to wire it in or
to declare it an exception below, with the reason.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from voxtrama.engine.skill_catalog import GENERATIVE_SKILL_NAMES

WORKFLOWS = Path(__file__).parents[1] / "workflows"

# Registered skills that no workflow names on purpose. Empty: if a skill
# serves no workflow, this list is where that question belongs.
DELIBERATELY_UNREACHED: frozenset[str] = frozenset()


def _skills_named_by_workflows() -> set[str]:
    named: set[str] = set()
    for path in sorted(WORKFLOWS.glob("*.yaml")):
        definition = yaml.safe_load(path.read_text())
        for step in definition.get("steps") or []:
            named.add(step["skill"])
            for alternative in (step.get("allows") or {}).get("skills") or []:
                named.add(alternative["skill"])
    return named


def test_every_registered_generative_skill_is_named_by_some_workflow() -> None:
    unreachable = set(GENERATIVE_SKILL_NAMES) - _skills_named_by_workflows()
    assert unreachable - DELIBERATELY_UNREACHED == set(), (
        f"skill registrate che nessun workflow esegue: {sorted(unreachable)}"
    )


def test_summarize_is_one_of_them() -> None:
    """The concrete case the general test grew from, kept by name.

    The test above would stay green if `summarize` left
    GENERATIVE_SKILL_NAMES as well as the workflows. This one says that
    summarizing is something the product does.
    """
    assert "summarize" in _skills_named_by_workflows()
