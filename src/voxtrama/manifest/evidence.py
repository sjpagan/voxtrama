"""How many claims a run produced, and how many of them still need review.

ClaimCount is engine.anchoring's own return type as much as this file's:
it lives here, not in engine, because where it is going is the manifest,
and manifest never depends on engine (see tests/test_architecture.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


@dataclass
class ClaimCount:
    """How many claims one step's output carried,
    and how many of them engine.anchoring could not anchor to the transcript.
    """

    claims: int
    needs_review: int


class ManifestEvidence(BaseModel):
    """The run-level sum of every step's ClaimCount.

    Always present in a manifest, never None: a run with no claims reports
    zero, which is the truth, not an absence.
    """

    model_config = ConfigDict(extra="forbid")
    claims: int
    needs_review: int


def evidence_info(counts: dict[str, ClaimCount]) -> ManifestEvidence:
    """Sum every step's ClaimCount into the run-level total the manifest reports."""
    return ManifestEvidence(
        claims=sum(count.claims for count in counts.values()),
        needs_review=sum(count.needs_review for count in counts.values()),
    )
