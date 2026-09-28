"""What a rejected run choice looks like, and how it reads.

Lives in workflow/, not engine/: this is the shape engine.choice_check
*produces*, but not one it owns. The route of the next issue will import
ChoicesRejected and its message to build a 422 detail, and has
no reason to import engine.choice_check's rules to do that. For the same
reason RunChoices (workflow.choices) lives here rather than in engine/.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rejection:
    """One choice that contradicts a constraint a skill or a step declared."""

    field: str
    value: str
    declared_by: str
    constraint: str


class ChoicesRejected(RuntimeError):
    """Run choices that contradict a constraint declared higher up.

    Carries every Rejection found, not just the first: engine.validation's
    validate_output already collects every schema error into one message
    instead of making a caller fix them one round trip at a time, and a
    rejected run choice deserves the same courtesy: three round trips for
    three errors are two too many for the interface that will show them.
    """

    def __init__(self, rejections: list[Rejection]) -> None:
        self.rejections = rejections
        super().__init__("; ".join(_describe(rejection) for rejection in rejections))


def _describe(rejection: Rejection) -> str:
    return (
        f"{rejection.declared_by} declares {rejection.constraint}; "
        f"the run chose {rejection.field} '{rejection.value}'"
    )
