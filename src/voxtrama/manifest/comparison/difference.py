"""Difference: one raw disagreement between two manifests, and the catalog of expected ones.

walk.py produces these without judging them. The catalog here is what turns
a Difference into "expected" (ignored, with a count) or left to count
against the run. Kept apart from walk.py because the catalog is a decision
about the *shape* of a manifest, while walk.py only knows how to
compare two dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class _Absent:
    """Marks a key or list item present in only one of the two manifests.

    Not `None`: `None` is a real value a manifest field can carry (
    `run.started_at` while a run is still pending), so the walker needs a
    marker that never equals anything an actual field holds.
    """

    def __repr__(self) -> str:
        return "(absent)"


ABSENT: Any = _Absent()


@dataclass(frozen=True)
class Difference:
    """One field where two manifest dicts disagree, named by its dotted/indexed path."""

    path: str
    before: Any
    after: Any


# A closed catalog of expected differences: everything else counts. Written as
# exact paths plus one suffix rule for steps[*], rather than a predicate per
# field, so the list itself is the specification: nothing to read past to
# know what is expected.
_EXPECTED_EXACT = frozenset(
    {
        "run.id",
        "run.created_at",
        "run.started_at",
        "run.finished_at",
        "run.destination.path",
        "input.recording_id",
    }
)
# duration_seconds is derived from started_at/finished_at: two runs
# whose timestamps are already expected to differ cannot be held to the
# same duration either, without that difference being the same non-fact
# twice.
_STEP_TIME_SUFFIXES = (".started_at", ".finished_at", ".duration_seconds")


def is_expected(path: str) -> bool:
    """Whether `path` is in the catalog of differences two runs may legitimately show.

    Two deliberate omissions:

    - `input.duration_seconds` is a property of the input, not of the run,
      even though it is a duration. If it changes, the two runs did not
      process the same audio, which this comparison must not hide.
    - `run.destination.root` is the root's label, not an identifier. A
      run that wrote under a different root is a real difference.

    `outputs[*].sha256` belongs here too, unconditionally, rather
    than on determinism.py's gate: it hashes output.json, and output.json
    embeds `run_id` by construction (manifest/output.py's RunOutput), so
    that hash can never match between two runs. It carries an identifier
    inside it, like `run.destination.path` above, and says nothing about
    whether a step's content changed. That
    judgment is what `steps[<id>].output_sha256` is for, and it stays on
    the gate instead (comparison/determinism.py).
    """
    if path in _EXPECTED_EXACT:
        return True
    if path.startswith("steps[") and path.endswith(_STEP_TIME_SUFFIXES):
        return True
    return path.startswith("outputs[") and path.endswith(".sha256")
