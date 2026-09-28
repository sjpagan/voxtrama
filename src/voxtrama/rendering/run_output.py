"""GET /runs/{id}/view's "Verified output" cards, for a succeeded run.

Reads output.json's keys against the four generative skills the
package ships (engine.skill_catalog.GENERATIVE_SKILL_NAMES), not a
business-level list of "kinds" invented for this page: skills/
extract_decisions.yaml produces one flat array, "decisions", each item
carrying "decision" (a full sentence); skills/extract_concepts.yaml
produces "concepts", each carrying "concept" and "definition";
skills/extract_themes.yaml produces "themes", each carrying "theme" and
"insight"; skills/summarize.yaml produces "key_points", each carrying only
"text".

The design's split (Decision, Action item, Open question) matches none
of these schemas: extract_decisions' output has no field that tells them
apart, so every decision renders as "Decision".

Every claim already carries `evidence` and `needs_review`, written by
engine.anchoring right after the step that produced it returned. This
module only reads them and never re-anchors or recomputes either.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voxtrama.humanize import human_clock
from voxtrama.manifest.output import RunOutput
from voxtrama.manifest.schema import Manifest


@dataclass(frozen=True)
class _ClaimKind:
    """Which array a skill's output carries claims under, which of a
    claim's fields is its heading (None for a claim with no separate
    one) and its body text, and which of the four card colours it wears."""

    kind: str
    text_field: str
    color: int
    heading_field: str | None = None


# One entry per generative skill's output_schema (module docstring).
# `color` is fixed per kind, so every "Decision" card wears the same one.
_CLAIM_KINDS: dict[str, _ClaimKind] = {
    "decisions": _ClaimKind(kind="decision", text_field="decision", color=1),
    "concepts": _ClaimKind(
        kind="concept", text_field="definition", heading_field="concept", color=2
    ),
    "themes": _ClaimKind(kind="theme", text_field="insight", heading_field="theme", color=3),
    "key_points": _ClaimKind(kind="key_point", text_field="text", color=4),
}


@dataclass(frozen=True)
class ProvenanceView:
    """Which workflow, skill and model produced one card (the
    manifest's provenance fields). `model` is None for a step whose provenance was
    never recorded (see ManifestStep's docstring for why)."""

    workflow: str
    skill: str
    model: str | None


@dataclass(frozen=True)
class OutputItemView:
    """One claim, as a "Verified output" card shows it. `evidence_label` is None exactly when
    `needs_review` is True for lack of an anchor. `kind_color` cycles
    through the four --vx-speaker-1..4 tokens, coloured by the shape the
    data has (the module docstring says why not by the design's split)."""

    kind: str
    kind_color: int
    heading: str | None
    text: str
    needs_review: bool
    evidence_start: float | None
    evidence_end: float | None
    evidence_label: str | None
    provenance: ProvenanceView
    evidence_speaker: str | None = None  # Filled by rendering.run_result
    # `<step>/<array>/<index>`, what a correction names (manifest.edits),
    # and whether a person corrected this point.
    ref: str = ""
    edited: bool = False

    @property
    def evidence_time(self) -> str | None:
        """Where the evidence starts, the time at the top right of a card."""
        return human_clock(self.evidence_start) if self.evidence_start is not None else None


def _evidence_label(start: float | None, end: float | None) -> str | None:
    if start is None or end is None:
        return None
    return f"{human_clock(start)}-{human_clock(end)}"


# The field manifest.edits.apply_edits rewrites, per array.
TEXT_FIELDS = {key: kind.text_field for key, kind in _CLAIM_KINDS.items()}


def _claim_view(
    claim: dict[str, Any], kind: _ClaimKind, provenance: ProvenanceView, ref: str = ""
) -> OutputItemView:
    evidence = claim.get("evidence") or {}
    start, end = evidence.get("start"), evidence.get("end")
    return OutputItemView(
        kind=kind.kind,
        kind_color=kind.color,
        heading=claim.get(kind.heading_field) if kind.heading_field else None,
        text=claim.get(kind.text_field, ""),
        needs_review=bool(claim.get("needs_review")),
        evidence_start=start,
        evidence_end=end,
        evidence_label=_evidence_label(start, end),
        provenance=provenance,
        ref=ref,
        edited=bool(claim.get("edited")),
    )


def output_items(manifest: Manifest, output: RunOutput) -> tuple[OutputItemView, ...]:
    """Every claim `output` carries, one card per item, in manifest.steps
    order (already by position, from manifest.builder.build_manifest's
    sort). A step whose output has none of `_CLAIM_KINDS`' arrays
    (transcribe, diarize, a deterministic step) contributes nothing."""
    items: list[OutputItemView] = []
    for step in manifest.steps:
        produced = output.steps.get(step.step_id)
        if not produced:
            continue
        provenance = ProvenanceView(
            workflow=manifest.workflow.name, skill=step.skill, model=step.model
        )
        for key, kind in _CLAIM_KINDS.items():
            claims = produced.get(key)
            if not isinstance(claims, list):
                continue
            items.extend(
                _claim_view(claim, kind, provenance, f"{step.step_id}/{key}/{index}")
                for index, claim in enumerate(claims)
            )
    return tuple(items)
