"""Adopting a source run's output as this run's own, without running the step.

Split from engine.reuse, which decides *whether* an output can be reused
(the lookup, the schema check). This module is what happens once the
answer is yes. The split follows the project's line limit and the separation
engine.anchoring and engine.validation already keep.

Two rules live here and nowhere else:

**Provenance is inherited, never invented.** A reused step ran nothing, so
the true provenance is the source run's: model, model_revision, provider,
host and profile_check_skipped are copied across as they are. That
includes diarize's `model_revision` of None, which is true (the
ECAPA-TDNN weights pin no revision) and must not be confused with
the None of a row whose provenance was never recorded.

**Evidence is re-anchored, never inherited.** The manifest sums evidence
at run level (manifest/evidence.py), so no per-step count exists to carry
over. Re-anchoring is also the check that the reuse was legitimate: an
output that no longer matches this run's transcript raises
EvidenceNotAnchored, and the run fails honestly instead of adopting an
orphaned evidence count.
"""

from __future__ import annotations

from typing import Any

from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Transcript
from voxtrama.engine.anchoring import EvidenceNotAnchored, anchor_output
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress import mark_succeeded, record_provenance
from voxtrama.workflow.definition import Step
from voxtrama.workflow.skill import Skill


def _adopt_transcript(context: ExecutionContext, output: dict[str, Any]) -> None:
    """Make the transcript a reused output carries this run's own.

    Deliberately generic: any output with a `transcript_id` counts, with no
    `if step.skill == ...` anywhere. The engine does not know skill names,
    and a skill written next year that produces a transcript must work
    here without this file learning its name.

    Called before anchoring, never after: an output that carries its own
    transcript has to be anchored against that one. A reused transcribe
    would otherwise anchor against whatever the run held so far, which for
    the first step of a run is nothing.
    """
    transcript_id = output.get("transcript_id")
    if transcript_id is not None:
        context.transcript = context.session.get(Transcript, transcript_id)


def apply_reused_output(
    context: ExecutionContext,
    step: Step,
    row: RunStep,
    skill: Skill,
    source_row: RunStep,
    output: dict[str, Any],
) -> None:
    """Adopt `output` as if `step` had just produced it, without running it again.

    Re-anchors rather than inheriting evidence: the manifest
    sums evidence at run level (manifest/evidence.py), so there is no
    per-step count to carry over. anchor_output re-derives
    context.evidence[step.id] against the current transcript, like a
    freshly-executed step. If it raises EvidenceNotAnchored, the reused
    output no longer matches this run's transcript, and the run fails
    honestly instead of adopting an orphaned evidence count.

    Adopts the output's own transcript first (_adopt_transcript), then
    anchors against it.

    _inherit_provenance decides where the row's provenance comes from.
    """
    _adopt_transcript(context, output)
    try:
        context.evidence[step.id] = anchor_output(skill, context.transcript, output)
    except EvidenceNotAnchored as exc:
        context.evidence[step.id] = exc.count
        raise
    context.produced[step.id] = output
    _inherit_provenance(context, row, source_row)
    mark_succeeded(context.session, row)


def _inherit_provenance(context: ExecutionContext, row: RunStep, source_row: RunStep) -> None:
    """Copy the source step's provenance onto `row`, and record where it came from.

    Verbatim, never invented: a reused step ran nothing, so
    `source_row`'s model/model_revision/provider/host/profile_check_skipped
    are the true ones. That includes a None model_revision which is itself
    a fact (diarize's ECAPA-TDNN pins no revision), not the None of a
    row whose provenance was never recorded.

    `reused_from_run_id` is read off `source_row`, not off the run's
    request. The column on Run says what was asked for. The one on RunStep
    says where this artefact came from, and must stay true when the lookup
    widens past a single source run.
    """
    record_provenance(
        context.session,
        row,
        model=source_row.model,
        model_revision=source_row.model_revision,
        provider=source_row.provider,
        host=source_row.host,
        profile_check_skipped=source_row.profile_check_skipped,
    )
    row.reused_from_run_id = source_row.run_id
