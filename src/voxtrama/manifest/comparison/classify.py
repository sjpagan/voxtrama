"""Sorts walk.py's raw differences into counted, expected, and gated.

Split from report.py to stay under the project's 150-line limit: the gated
bucket has a second, per-step question to answer: `steps[<id>].output_sha256`
against that step's own determinism, not just `evidence.claims`/
`evidence.needs_review` against the whole run's (determinism.py's docstring
explains why both still exist). That decision got its own file rather
than pushing report.py past the limit.
"""

from __future__ import annotations

from voxtrama.manifest.comparison.determinism import non_reproducible_reason, output_hash_reason
from voxtrama.manifest.comparison.difference import Difference, is_expected

# The aggregates non_reproducible_reason (the whole-run gate) still judges:
# see determinism.py's docstring for why these two stay aggregate while
# steps[*].output_sha256 moved to a per-step gate.
_GATED_EXACT = {"evidence.claims", "evidence.needs_review"}
_STEP_OUTPUT_HASH_PREFIX = "steps["
_STEP_OUTPUT_HASH_SUFFIX = "].output_sha256"


def classify(
    differences: list[Difference], a: dict, b: dict
) -> tuple[list[Difference], list[Difference], list[tuple[Difference, str]]]:
    """Split `differences` into counted, expected (difference.py's catalog), and gated.

    A `steps[<id>].output_sha256` difference and an `evidence.claims`/
    `evidence.needs_review` one are gated by two different questions (the
    step's own determinism versus the whole run's), so each gated
    Difference carries its own reason rather than one reason shared by the
    whole bucket.
    """
    counted, expected, gated = [], [], []
    aggregate_reason = non_reproducible_reason(a, b)
    for diff in differences:
        if is_expected(diff.path):
            expected.append(diff)
            continue
        reason = _gate_reason(diff.path, a, b, aggregate_reason)
        if reason is not None:
            gated.append((diff, reason))
        else:
            counted.append(diff)
    return counted, expected, gated


def _gate_reason(path: str, a: dict, b: dict, aggregate_reason: str | None) -> str | None:
    step_id = _step_output_hash_id(path)
    if step_id is not None:
        return output_hash_reason(step_id, a, b)
    if path in _GATED_EXACT:
        return aggregate_reason
    return None


def _step_output_hash_id(path: str) -> str | None:
    if path.startswith(_STEP_OUTPUT_HASH_PREFIX) and path.endswith(_STEP_OUTPUT_HASH_SUFFIX):
        return path[len(_STEP_OUTPUT_HASH_PREFIX) : -len(_STEP_OUTPUT_HASH_SUFFIX)]
    return None
