"""Re-anchors a step's claims to the transcript they cite.

A claim is a dict, anywhere inside a step's output, carrying a `quote`
string. The rule: an extractive skill's declared interval is
*verified* against the transcript. A generative skill's declared interval
is discarded and the quote is *located* instead, because a generative
model asked to cite a timestamp invents plausible ones. Either way this
file writes `evidence` and `needs_review` onto every claim it finds. That
is the engine's job, not a skill's, so no skill can forget it.

Retrying an anchoring failure buys nothing. On a generative skill
run_with_retry (engine.retry) already forbids the retry, and
on an extractive one nothing here samples, so a second attempt finds what
the first one found. EvidenceNotAnchored crosses run_with_retry like any
other exception, with no special-cased retry.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from voxtrama.db.models.transcript import Transcript
from voxtrama.engine.anchor_index import AnchorIndex, build_index
from voxtrama.manifest.evidence import ClaimCount
from voxtrama.workflow.skill import ModelClass, Skill

# A fragment, not a standalone schema: a skill merges CLAIM_SCHEMA's
# "properties" and "required" into its own claim object schema, so that a
# claim with `additionalProperties: false` can still declare the two keys
# the engine writes (evidence, needs_review) alongside whatever fields the
# skill itself owns (text, label, ...).
CLAIM_SCHEMA: dict[str, Any] = {
    "properties": {
        "quote": {"type": "string"},
        "evidence": {
            "type": ["object", "null"],
            "properties": {"start": {"type": "number"}, "end": {"type": "number"}},
        },
        "needs_review": {"type": "boolean"},
    },
    "required": ["quote"],
}


class EvidenceNotAnchored(RuntimeError):
    """A skill declares evidence_required, and at least one claim did not anchor.

    Carries the ClaimCount already computed for the step: engine.preparation
    records it into ExecutionContext before re-raising, so a run that fails
    here still says how many claims were appended.
    """

    def __init__(self, message: str, count: ClaimCount) -> None:
        super().__init__(message)
        self.count = count


def anchor_output(
    skill: Skill, transcript: Transcript | None, output: dict[str, Any]
) -> ClaimCount:
    """Anchor every claim in `output` to `transcript`, mutating it in place.

    Runs in engine.preparation.execute_step right after validate_output:
    only a value that already matches its skill's output_schema is safe to
    walk and rewrite here. Without a transcript, nothing anchors and every
    claim comes back needs_review.
    """
    index = build_index(transcript) if transcript is not None else None
    claims = 0
    unanchored = 0
    for claim in iter_claims(output):
        claims += 1
        if not _anchor_claim(skill, index, claim):
            unanchored += 1
    count = ClaimCount(claims=claims, needs_review=unanchored)
    if skill.evidence_required and unanchored:
        raise EvidenceNotAnchored(
            f"{skill.name}@{skill.version}: {unanchored} of {claims} claim(s) not anchored", count
        )
    return count


def iter_claims(node: Any) -> Iterator[dict[str, Any]]:
    """Yield every claim found anywhere inside `node`, at any depth.

    A claim is a dict whose `quote` value is a string. Recurses into
    dict values and list items only: a claim's `quote` is a leaf, and dict
    keys never carry claims by this convention.

    Public because calibration.anchoring walks the same output.json
    this file wrote `evidence` and `needs_review` onto, and must find
    exactly the claims this engine anchored. A second implementation of
    this walk would drift and start counting claims the engine never
    touched.
    """
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str):
            yield node
        for value in node.values():
            yield from iter_claims(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_claims(item)


def _anchor_claim(skill: Skill, index: AnchorIndex | None, claim: dict[str, Any]) -> bool:
    """Write `evidence` and `needs_review` onto `claim` in place; return whether it anchored."""
    interval = None
    if index is not None:
        if skill.model_class == ModelClass.EXTRACTIVE:
            interval = _extractive_interval(index, claim.get("evidence"), claim["quote"])
        else:
            interval = index.find_interval(claim["quote"])
    claim["evidence"] = {"start": interval[0], "end": interval[1]} if interval else None
    claim["needs_review"] = interval is None
    return interval is not None


def _extractive_interval(
    index: AnchorIndex, declared: Any, quote: str
) -> tuple[float, float] | None:
    """The skill's declared [start, end) if it verifies, else None.

    Never falls back to searching for the quote by text: an extractive
    skill that fails to produce a usable interval has not done its job,
    and a text search here would quietly do that job for it.
    """
    if not isinstance(declared, dict):
        return None
    start, end = declared.get("start"), declared.get("end")
    numeric = (int, float)
    if not isinstance(start, numeric) or not isinstance(end, numeric):
        return None
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if start > end or not index.covers(start, end, quote):
        return None
    return float(start), float(end)
