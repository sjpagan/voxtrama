"""Turns a run's manifest and output.json into an AnchoringReport.

Split from anchoring.py's measure_run (which only locates the two files
and decides RunMaterialStatus) for the project's file and function line
limits. This file assumes both are already resolved, and only walks
manifest.steps against output.steps to build the two measures (unanchored
claims, evidence coverage). calibration/anchoring_report.py has their
exact shape.

Reuses engine.anchoring.iter_claims rather than re-walking output.json's
tree (see that function's docstring): two implementations
of the same walk would drift, and this measure would start counting
claims the engine itself never anchored, or the reverse.
"""

from __future__ import annotations

from voxtrama.calibration.anchoring_report import (
    AnchoringMeasure,
    AnchoringReport,
    RunMaterialStatus,
    SkillKey,
)
from voxtrama.engine.anchoring import iter_claims
from voxtrama.manifest.output import RunOutput
from voxtrama.manifest.schema import Manifest
from voxtrama.workflow.skill import Determinism

_SkillTotals = dict[SkillKey, list[int]]
_SkillDeterminism = dict[SkillKey, Determinism | None]


def walk_steps(manifest: Manifest, output: RunOutput) -> AnchoringReport:
    """Build a MEASURED AnchoringReport from a run's own manifest and output.json.

    A step whose output.json entry is absent (skipped by its condition,
    or failed before producing anything) is left out of per_step and
    per_skill rather than counted as zero claims. Its step_id goes into
    `skipped_steps` instead: a failed generative
    step must not vanish from the report, as it would if "no output" and
    "zero claims" were the same row.
    """
    per_step, totals, skill_deterministic, skipped = _walk(manifest, output)
    per_skill = _finalize_skills(totals, skill_deterministic)
    return AnchoringReport(
        status=RunMaterialStatus.MEASURED,
        per_step=per_step,
        per_skill=per_skill,
        skipped_steps=tuple(skipped),
    )


def _walk(
    manifest: Manifest, output: RunOutput
) -> tuple[dict[str, AnchoringMeasure], _SkillTotals, _SkillDeterminism, list[str]]:
    """One pass over manifest.steps: per_step, running per-skill totals, and skipped step_ids."""
    per_step: dict[str, AnchoringMeasure] = {}
    totals: _SkillTotals = {}
    skill_deterministic: _SkillDeterminism = {}
    skipped: list[str] = []
    for step in manifest.steps:
        produced = output.steps.get(step.step_id)
        if produced is None:
            skipped.append(step.step_id)
            continue
        claims, needs_review = _count_claims(produced)
        per_step[step.step_id] = AnchoringMeasure(claims, needs_review, step.deterministic)
        key = SkillKey(step.skill, step.skill_version)
        counted = totals.setdefault(key, [0, 0])
        counted[0] += claims
        counted[1] += needs_review
        # Overwritten on every matching step, not merged. This is safe
        # because a skill's determinism follows only from its name+version
        # (Skill.deterministic is computed from model_class alone, see
        # workflow/skill.py), so two steps sharing a SkillKey always write
        # the same value here.
        skill_deterministic[key] = step.deterministic
    return per_step, totals, skill_deterministic, skipped


def _finalize_skills(
    totals: _SkillTotals, skill_deterministic: _SkillDeterminism
) -> dict[SkillKey, AnchoringMeasure]:
    return {
        key: AnchoringMeasure(claims, needs_review, skill_deterministic[key])
        for key, (claims, needs_review) in totals.items()
    }


def _count_claims(produced: dict) -> tuple[int, int]:
    """(claims, needs_review) for one step's produced output, via engine.anchoring's own walk."""
    claims = 0
    needs_review = 0
    for claim in iter_claims(produced):
        claims += 1
        if claim.get("needs_review"):
            needs_review += 1
    return claims, needs_review
