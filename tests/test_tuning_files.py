"""Every shipped tuning/*.yaml must validate against its own schema.

A broken file shipped with the product is worse than one a user wrote:
nobody chose to break it, and doctor never gets a chance to say so before
it is already in the release.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.tuning.definition import TuningFile
from voxtrama.workflow.document import DocumentError, read_document

REPO_ROOT = Path(__file__).resolve().parents[1]
TUNING_DIR = REPO_ROOT / "tuning"


def test_tuning_directory_is_not_empty() -> None:
    assert list(TUNING_DIR.glob("*.yaml"))


def test_every_shipped_tuning_file_validates() -> None:
    failures = []
    for path in sorted(TUNING_DIR.glob("*.yaml")):
        try:
            read_document(path, TuningFile)
        except DocumentError as exc:
            failures.append(str(exc))
    assert not failures, "\n".join(failures)


def test_exactly_one_shipped_file_declares_no_conditions() -> None:
    """The generic fallback: nothing else may leave a machine untuned by accident."""
    generic = []
    for path in sorted(TUNING_DIR.glob("*.yaml")):
        tuning_file = read_document(path, TuningFile)
        if not tuning_file.applies_to.model_dump(exclude_none=True):
            generic.append(path.name)
    assert generic == ["generic.yaml"]
