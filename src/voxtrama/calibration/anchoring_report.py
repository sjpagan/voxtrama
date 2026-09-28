"""The shape of one run's anchoring measures: dataclasses only, no computation.

Split from anchoring.py the same way manifest/schema.py splits from
manifest/writer.py (see their docstrings). The result's shape lives here
so a caller that only type-hints against AnchoringReport
(cli/commands/calibrate_run.py, a future command) does not pull in
measure_run's file-reading logic. The two together crossed the project's
150-line limit, so they were split rather than compressed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from voxtrama.workflow.skill import Determinism


class RunMaterialStatus(StrEnum):
    """Why `measure_run` can, or cannot yet, report anchoring measures for a run.

    calibration.anchoring's DatasetStatus (calibration/dataset.py): what
    is missing is a value a caller reads, never an exception a caller
    must remember to catch. calibration.dataset has the same shape, for
    the same reason. A caller of measure_run
    that forgets a try/except must not turn "this run has not produced
    anything yet" into a 500.
    """

    MANIFEST_MISSING = "manifest_missing"
    OUTPUT_MISSING = "output_missing"
    MEASURED = "measured"


@dataclass(frozen=True)
class SkillKey:
    """A skill identified by name and version together."""

    name: str
    version: str


@dataclass(frozen=True)
class AnchoringMeasure:
    """Claim counts for one step or one skill, and the coverage they imply.

    `deterministic` carries Skill.deterministic: the one
    reproducibility fact the manifest already records honestly, used here
    only to mark a row, never invented for a classification that has no
    other honest criterion.
    """

    claims: int
    needs_review: int
    deterministic: Determinism | None

    @property
    def coverage(self) -> float | None:
        """The anchored fraction, or None when there are no claims to measure."""
        if self.claims == 0:
            return None
        return (self.claims - self.needs_review) / self.claims


@dataclass(frozen=True)
class AnchoringReport:
    """Per-step and per-skill anchoring measures for one run, or why there are none yet.

    `per_step`, `per_skill` and `skipped_steps` are only meaningful when
    `status` is MEASURED. Otherwise they are empty, never partially
    filled. A caller checks `status` first, as
    calibration.dataset.DatasetReport asks of its callers.
    """

    status: RunMaterialStatus
    per_step: dict[str, AnchoringMeasure]
    per_skill: dict[SkillKey, AnchoringMeasure]
    # step_id of every step whose output.json entry is absent: skipped by
    # its condition, or failed before producing anything. Left out of
    # per_step rather than counted as zero claims, since a step with no
    # output has no claims to measure. Named here so a failed generative
    # step's row is never silently missing from a report that would
    # otherwise read as "all clear".
    skipped_steps: tuple[str, ...]
