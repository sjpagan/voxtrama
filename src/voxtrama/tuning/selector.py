"""Picks which tuning/*.yaml applies to a machine.

Reads every file the two tuning roots offer (the data directory's own
tuning/ winning by name over the package's), keeps the ones whose declared
conditions the machine satisfies, and returns the most specific: the one
declaring the most conditions among those satisfied. The generic file
declares none, so it always qualifies and no machine is left untuned. A
tie at the top score is never broken arbitrarily (see TuningConflictError).
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.tuning.definition import TuningConditions, TuningFile
from voxtrama.tuning.errors import TuningConflictError, TuningNotFoundError, TuningValidationError
from voxtrama.workflow.document import DocumentError, document_roots, read_document


def _candidate_files() -> list[Path]:
    """Every tuning/*.yaml across both roots, first occurrence of a name wins.

    document_roots("tuning") lists the data directory before the package's
    own, so a user's override is already first. This only has to keep the
    first Path it sees for each filename.
    """
    seen: dict[str, Path] = {}
    for root in document_roots("tuning"):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.yaml")):
            seen.setdefault(path.name, path)
    return list(seen.values())


def _load(path: Path) -> TuningFile:
    try:
        return read_document(path, TuningFile)
    except DocumentError as exc:
        raise TuningValidationError(str(exc)) from exc


def _matches(conditions: TuningConditions, machine: MachineReport) -> bool:
    if conditions.architecture is not None and conditions.architecture != machine.architecture:
        return False
    if conditions.accelerator is not None:
        wanted = None if conditions.accelerator == "none" else conditions.accelerator.value
        if wanted != machine.accelerator:
            return False
    if conditions.unified_memory is not None:
        if conditions.unified_memory != machine.unified_memory:
            return False
    return True


def _specificity(conditions: TuningConditions) -> int:
    return sum(1 for value in conditions.model_dump().values() if value is not None)


def select_tuning(machine: MachineReport) -> TuningFile:
    """The most specific tuning file whose declared conditions `machine` satisfies."""
    loaded = [(path, _load(path)) for path in _candidate_files()]
    applicable = [(path, tf) for path, tf in loaded if _matches(tf.applies_to, machine)]
    if not applicable:
        raise TuningNotFoundError("no tuning file applies to this machine, not even a generic one")
    best = max(_specificity(tf.applies_to) for _, tf in applicable)
    winners = [(path, tf) for path, tf in applicable if _specificity(tf.applies_to) == best]
    if len(winners) > 1:
        names = ", ".join(str(path) for path, _ in winners)
        raise TuningConflictError(f"{len(winners)} tuning files tie at specificity {best}: {names}")
    return winners[0][1]
