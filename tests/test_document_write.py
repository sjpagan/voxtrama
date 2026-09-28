"""Saving a domain document must not break what was there.

save_document is generic over the Pydantic model it writes, so these tests
use a tiny model of their own rather than a real domain schema: what is
being checked is the write mechanism, not any one document format.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

import voxtrama.workflow.document_write as document_write
from voxtrama.config.settings import get_settings
from voxtrama.workflow.document import read_document
from voxtrama.workflow.document_write import DocumentWriteError, save_document


class _Note(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


def test_a_saved_document_round_trips_exactly() -> None:
    """Accents, an emoji, a multi-line string and trailing spaces all survive.

    Compared as models, not as file text.
    """
    note = _Note(title="idée 💡", body="riga uno\nriga due   ")

    path = save_document("notes", "roundtrip", note)
    reread = read_document(path, _Note)

    assert reread == note


def test_a_saved_document_is_written_as_literal_utf8_not_escaped() -> None:
    """allow_unicode=True matters here: without it this finds \\xE8, not è."""
    note = _Note(title="caffè", body="ok")

    path = save_document("notes", "unicode", note)
    raw = path.read_text(encoding="utf-8")

    assert "è" in raw
    assert "\\xE8" not in raw
    assert "\\u00e8" not in raw


def test_a_failed_round_trip_leaves_the_previous_file_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A save whose reread does not match the original must not replace what was already there."""
    path = save_document("notes", "fragile", _Note(title="before", body="before"))
    before = path.read_bytes()

    def _mismatched_reread(*_args: object, **_kwargs: object) -> _Note:
        return _Note(title="not", body="what was written")

    monkeypatch.setattr(document_write, "read_document", _mismatched_reread)

    with pytest.raises(DocumentWriteError):
        save_document("notes", "fragile", _Note(title="after", body="after"))

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_save_document_never_writes_outside_the_data_directory() -> None:
    """Built from data_dir alone: the path never even points at the package root."""
    path = save_document("notes", "inside-data-dir", _Note(title="t", body="b"))

    assert path.is_relative_to(get_settings().data_dir)
    assert path == get_settings().data_dir / "notes" / "inside-data-dir.yaml"


def test_a_system_document_saved_over_produces_a_user_copy_and_leaves_the_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modifying a system document writes a covering copy. The package's file stays untouched."""
    package_root = tmp_path / "package"
    (package_root / "notes").mkdir(parents=True)
    system_file = package_root / "notes" / "shipped.yaml"
    system_file.write_text(_Note(title="shipped", body="shipped").model_dump_json())
    monkeypatch.chdir(package_root)
    original_bytes = system_file.read_bytes()

    saved = save_document("notes", "shipped", _Note(title="mine", body="mine"))

    assert saved == get_settings().data_dir / "notes" / "shipped.yaml"
    assert read_document(saved, _Note) == _Note(title="mine", body="mine")
    assert system_file.read_bytes() == original_bytes
