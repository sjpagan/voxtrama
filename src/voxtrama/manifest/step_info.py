"""Builds one steps[] entry from a RunStep: duration and output hash included.

Split from builder.py, which now only assembles the whole Manifest, to keep
that file under the project's size limit. ManifestStep lives in step.py rather
than in schema.py for the same reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from voxtrama.db.models.step import RunStep
from voxtrama.manifest.output import step_output_hash
from voxtrama.manifest.sections import iso_ms
from voxtrama.manifest.step import ManifestStep
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import ModelClass


def _as_utc(value: datetime) -> datetime:
    """`value`, guaranteed tz-aware in UTC.

    progress.py always writes `datetime.now(UTC)`, but SQLAlchemy expires a
    row on commit and SQLite's driver reads a naive datetime back. So the
    same RunStep can hold an aware started_at (just set, never reloaded)
    next to a naive finished_at (reread from the database), and subtracting
    them raises. Naive values are always this app's own UTC, never a
    different zone to guess at, so attaching UTC is not a guess.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _step_duration(row: RunStep) -> float | None:
    """The wall-clock time `row` took, or None while that cannot be known yet.

    None, never 0.0, when either timestamp is missing: a step that has not
    started or has not finished has no duration to report, the same
    rule diagnostics/machine.py applies to a reading it does not have.
    Rounded to three decimals, like input.duration_seconds, so two runs of
    the same input keep comparing on the same terms.
    """
    if row.started_at is None or row.finished_at is None:
        return None
    return round((_as_utc(row.finished_at) - _as_utc(row.started_at)).total_seconds(), 3)


def step_info(
    row: RunStep, skills: SkillRegistry, produced: dict[str, dict[str, Any]] | None
) -> ManifestStep:
    skill = skills.get(row.skill, {}).get(row.skill_version)
    return ManifestStep(
        step_id=row.step_id,
        skill=row.skill,
        skill_version=row.skill_version,
        state=str(row.state),
        # None only when the skill cannot be resolved (an unknown skill
        # fails the run before this can be derived): never written by
        # hand, always Skill.deterministic.
        deterministic=skill.deterministic if skill is not None else None,
        attempts=row.attempts,
        position=row.position,
        started_at=iso_ms(row.started_at),
        finished_at=iso_ms(row.finished_at),
        error=row.error,
        duration_seconds=_step_duration(row),
        output_sha256=step_output_hash(row.step_id, produced),
        # Read straight off the row, never off ExecutionContext.models:
        # engine.reconcile_manifest rebuilds a manifest from rows
        # alone, with no live ctx to read, and the row is exactly what
        # engine.progress.record_provenance already committed.
        model=row.model,
        model_revision=row.model_revision,
        provider=row.provider,
        host=row.host,
        profile_check_skipped=row.profile_check_skipped,
        # Same reasoning as model/provider above: read straight off
        # the row engine.preparation.execute_step already wrote, never
        # recomputed from a live ExecutionContext that reconcile_manifest
        # does not have.
        input_sha256=row.input_sha256,
        reuse_key=row.reuse_key,
        # Same reasoning: read straight off the row, never inferred
        # from Run.reused_from_run_id. See ManifestStep's comments.
        reused_from_run_id=row.reused_from_run_id,
        context_window_tokens=row.context_window_tokens,
        context_window_at_risk=row.context_window_at_risk,
        output_resumptions=row.output_resumptions,
        transcript_windows=row.transcript_windows,
    )


def is_generative(skills: SkillRegistry, row: RunStep) -> bool:
    """Whether `row` runs a skill that calls a text provider."""
    skill = skills.get(row.skill, {}).get(row.skill_version)
    if skill is None:
        return row.provider not in (None, "local")
    return skill.model_class == ModelClass.GENERATIVE
