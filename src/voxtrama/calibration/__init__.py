"""Calibration: whether the material `voxtrama calibrate` needs is there.

Kept separate from `diagnostics`: that package answers "can this machine
run Voxtrama", this one answers "does this material let us measure
Voxtrama". Both happen to be read-only inspections, but they answer
different questions about different things.
"""

from __future__ import annotations

from voxtrama.calibration.dataset import ClipMaterial, DatasetReport, DatasetStatus, read_dataset

__all__ = [
    "ClipMaterial",
    "DatasetReport",
    "DatasetStatus",
    "read_dataset",
]
