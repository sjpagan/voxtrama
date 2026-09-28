"""Which model weights a run will have to fetch before it can do anything.

Moved here from cli.preflight: the CLI needed it to announce a wait
before it starts ("an announced wait is a wait; an unannounced wait is a
fault"), and the engine needs the same figure to size a job's
timeout honestly. A byte count belongs to core, and core cannot
import from an entrypoint. Both now read it from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voxtrama.transcription import weights_for
from voxtrama.weights import WeightSet, ecapa_weights, is_cached
from voxtrama.workflow.definition import Workflow

DIARIZE_SKILL = "diarize"


@dataclass(frozen=True)
class PendingDownload:
    """A weight set this run will have to fetch, and roughly how big it is."""

    label: str
    nominal_bytes: int


def pending_downloads(workflow: Workflow, profile: str, models_dir: Path) -> list[PendingDownload]:
    """Which model weights this run will download before it can do anything.

    Only what the workflow uses: announcing the speaker model to
    someone running a transcribe-only workflow would be a warning about
    something that never happens, and those get ignored.
    """
    needed: list[WeightSet] = [weights_for(profile)]
    if any(step.skill == DIARIZE_SKILL for step in workflow.steps):
        needed.append(ecapa_weights())
    return [
        PendingDownload(label=weights.label, nominal_bytes=weights.nominal_bytes)
        for weights in needed
        if not is_cached(weights, models_dir)
    ]
