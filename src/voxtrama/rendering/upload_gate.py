"""Whether the upload box may accept anything, and what to say when it may not.

Until now the home page accepted a file on an installation with no model,
no resolvable hardware profile and possibly no writable data directory:
the upload succeeded and the fault surfaced later, inside a run, where it
is hardest to read. The extreme case: a recording transcribed
for eight minutes before dying on a table the database did not have.

This module does not read the machine and does not decide what "ready"
means: diagnostics.read_readiness and diagnostics.check_schema
already do both. It only turns their verdicts into what the box needs
(open or closed, and for each thing missing, why and where it is fixed),
the same split rendering.status_row keeps between a state and the tone
that stands for it.

**On the first-run principle.** "Zero mandatory decisions before the first
success" is the principle a gate can violate, and it was answered before
this code existed. The gate asks nobody to *decide* anything. It asks
that the guided setup has been run, and that setup measures and proposes
instead of asking. The one state that could have made this a trap (models_ready,
NOT_READY on every fresh install) is not one, because
/setup/local-processing downloads the weights itself, with the progress
a download has to show. That is the guided setup's step 5, one click
from the gate: the path forward, not a wall.

A later change shortened that path: while the machine's proposal is in
force, the home page's first-run card downloads the weights in one click
without leaving the page.

UNKNOWN closes the box exactly like NOT_READY: a state
nobody could read is not a state anybody verified.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.diagnostics.readiness import Readiness, ReadinessReport
from voxtrama.diagnostics.readiness_state import SchemaCheck

# Where each missing state is fixed. The ASR weights are
# downloaded by the local-processing step, not by the model-ready one:
# that step is the generative provider, a different thing with a
# similar name, and sending someone there would be a dead end.
_PROCESSING = "/setup/local-processing"
_STORAGE = "/setup/private-storage"

_FIX_HREF = {
    "local_processing": _PROCESSING,
    "models_ready": _PROCESSING,
    "private_storage": _STORAGE,
    # No page fixes a schema behind the code: it is a rebuild, run from a
    # terminal. The reason carries the command instead of a link.
    "schema": None,
}


@dataclass(frozen=True)
class BlockerView:
    """One reason the box is closed: which check, why, and where it is fixed."""

    key: str
    reason: str
    fix_href: str | None


@dataclass(frozen=True)
class UploadGateView:
    """Whether uploading is open, and everything standing in the way when it is not."""

    allowed: bool
    blockers: list[BlockerView]


def _blocker(key: str, state: Readiness, reason: str) -> BlockerView | None:
    if state is Readiness.READY:
        return None
    return BlockerView(key=key, reason=reason, fix_href=_FIX_HREF[key])


def upload_gate(report: ReadinessReport, schema: SchemaCheck) -> UploadGateView:
    """Close the upload box for every check that is not READY, naming each one."""
    candidates = [
        _blocker("local_processing", report.local_processing.state, report.local_processing.reason),
        _blocker("models_ready", report.models_ready.state, report.models_ready.reason),
        _blocker("private_storage", report.private_storage.state, report.private_storage.reason),
        _blocker("schema", schema.state, schema.reason),
    ]
    blockers = [blocker for blocker in candidates if blocker is not None]
    return UploadGateView(allowed=not blockers, blockers=blockers)
