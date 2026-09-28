"""Inventory of the calibration material at `VOXTRAMA_EVAL_DIR`.

`voxtrama calibrate` measures a model against this material, but the
measure itself happens elsewhere. This module answers a narrower
question (what is there, and why not if it is not) by reading
`reference.csv` and looking at file names, never a clip's own audio. It
never raises: an unset `eval_dir`, a path that does not exist, a missing
`reference.csv`, one with the wrong columns, or a clip with no annotation
yet, are all facts `DatasetStatus` reports, never an exception a caller
has to catch (an error must name its real cause, not the nearest
plausible one).

Reads the same curated corpus `tests/test_eval_set.py` guards and the
`eval_dir` fixture in `tests/conftest.py` requires: `reference.csv` at
the root plus `clips/`, not the loose `<id>.wav`/`<id>.rttm` pairs
`tests/test_transcription_asr.py` reads on its own: those are raw ASR
material (diarization reference, not this corpus). See docs/evaluation-set.md.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REFERENCE_FILENAME = "reference.csv"
# Repeated from tests/test_eval_set.py's EXPECTED_COLUMNS rather than
# imported: a guard that reads its expectation from the code it guards
# stops noticing drift. The two must stay equal.
REFERENCE_COLUMNS = ["clip", "speakers", "overlap", "language", "duration_s", "notes"]
CLIPS_DIRNAME = "clips"
REVISION_FILENAME = "REVISION"
ANNOTATION_SUFFIX = ".annotation.yaml"


class DatasetStatus(StrEnum):
    """Why `eval_dir` does, or does not, offer a curated corpus to inspect."""

    UNSET = "unset"
    DIRECTORY_MISSING = "directory_missing"
    REFERENCE_MISSING = "reference_missing"
    REFERENCE_MALFORMED = "reference_malformed"
    READY = "ready"


@dataclass(frozen=True)
class ClipMaterial:
    """One row of `reference.csv`, and whether its clip and annotation exist.

    `clip` is the file name exactly as `reference.csv` lists it (with its
    extension), matching `tests/test_eval_set.py`'s own convention.
    """

    clip: str
    has_clip: bool
    has_annotation: bool


@dataclass(frozen=True)
class DatasetReport:
    """What `eval_dir` offers today, and why not if `status` is not READY.

    `reference_columns` is only set for REFERENCE_MALFORMED: the header
    `reference.csv` has, so a caller can say what was expected
    against what was found instead of just "wrong".
    """

    eval_dir: Path | None
    status: DatasetStatus
    clips: tuple[ClipMaterial, ...]
    revision: str | None
    reference_columns: tuple[str, ...] | None = None

    @property
    def annotated(self) -> tuple[ClipMaterial, ...]:
        """Clips that already carry an annotation file."""
        return tuple(clip for clip in self.clips if clip.has_annotation)


def read_dataset(eval_dir: Path | None) -> DatasetReport:
    """Inspect `eval_dir`'s curated corpus (`reference.csv` + `clips/`).

    Each way this can fail to offer a ready corpus gets its own status
    instead of collapsing into one boolean: "not set" and "set
    but the material isn't built yet" send a person to fix different
    things. The command decides what to print for each status.
    """
    if eval_dir is None:
        return DatasetReport(eval_dir=None, status=DatasetStatus.UNSET, clips=(), revision=None)
    if not eval_dir.is_dir():
        return _empty(eval_dir, DatasetStatus.DIRECTORY_MISSING)
    reference = eval_dir / REFERENCE_FILENAME
    if not reference.is_file():
        return _empty(eval_dir, DatasetStatus.REFERENCE_MISSING)
    rows, columns = _read_reference(reference)
    if columns != REFERENCE_COLUMNS:
        return DatasetReport(
            eval_dir=eval_dir,
            status=DatasetStatus.REFERENCE_MALFORMED,
            clips=(),
            revision=None,
            reference_columns=tuple(columns),
        )
    clips = tuple(_clips(eval_dir, rows))
    return DatasetReport(
        eval_dir=eval_dir, status=DatasetStatus.READY, clips=clips, revision=_revision(eval_dir)
    )


def _empty(eval_dir: Path, status: DatasetStatus) -> DatasetReport:
    return DatasetReport(eval_dir=eval_dir, status=status, clips=(), revision=None)


def _read_reference(reference: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Every row of `reference.csv`, and the header it was read with."""
    with reference.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    return rows, columns


def _clips(eval_dir: Path, rows: list[dict[str, str]]) -> list[ClipMaterial]:
    clips_dir = eval_dir / CLIPS_DIRNAME
    materials = []
    for row in rows:
        clip = row["clip"]
        stem = Path(clip).stem
        materials.append(
            ClipMaterial(
                clip=clip,
                has_clip=(clips_dir / clip).is_file(),
                has_annotation=(clips_dir / f"{stem}{ANNOTATION_SUFFIX}").is_file(),
            )
        )
    return materials


def _revision(eval_dir: Path) -> str | None:
    """The set's own declared revision (docs/evaluation-set.md), or None if unset."""
    path = eval_dir / REVISION_FILENAME
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None
