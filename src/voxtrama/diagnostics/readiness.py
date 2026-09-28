"""Whether the three claims status_cards.html makes are true.

components/status_cards.html says, unconditionally, for every install: local
processing runs, models are ready, storage is private. Its comment admits
why: "there is no probe here to lie, only three sentences". The checkmark
is rendered three times out of three, even on a fresh install that has
not downloaded a single model yet. The status row, the upload gate and
the setup wizard each need the same three answers,
and if each computed its own reading they would disagree about the same
machine the moment one took a shortcut.
So the reading happens here, once. Rendering only displays
what read_readiness returns, and never calculates.

Each check lives in its own module (readiness_engine, readiness_models,
readiness_storage) with the reasoning for how far it may probe without
costing a page render seconds or a download. This file only runs all
three together.
A value that cannot be read comes back UNKNOWN, never a plausible zero or
a False dressed up as "not ready", the same rule diagnostics.machine
already follows.
"""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.readiness_engine import check_local_processing
from voxtrama.diagnostics.readiness_models import check_models_ready
from voxtrama.diagnostics.readiness_state import (
    LocalProcessingCheck,
    ModelsReadyCheck,
    PrivateStorageCheck,
    Readiness,
    ReadinessReport,
)
from voxtrama.diagnostics.readiness_storage import check_private_storage

__all__ = [
    "LocalProcessingCheck",
    "ModelsReadyCheck",
    "PrivateStorageCheck",
    "Readiness",
    "ReadinessReport",
    "check_local_processing",
    "check_models_ready",
    "check_private_storage",
    "read_readiness",
]


def read_readiness(settings: Settings) -> ReadinessReport:
    """Run all three checks, so the status row, upload gate and setup wizard share one reading."""
    return ReadinessReport(
        local_processing=check_local_processing(settings),
        models_ready=check_models_ready(settings),
        private_storage=check_private_storage(settings),
    )
