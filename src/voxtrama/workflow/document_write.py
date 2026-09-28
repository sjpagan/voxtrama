"""Write a domain document without breaking what was there.

document.py answers "where does one live and what is inside it". This
module answers "how do you write one without breaking what was there".
Split off rather than appended to document.py because that file already
sits at the project's size limit. See its docstring for
what it still owns.

Writing is bound by the same restriction as reading: this touches domain
documents only, the ones a Pydantic model can validate. Nothing here should
ever be pointed at compose.yaml or a CI configuration: those have no model to
round-trip against, and save_document would happily overwrite either.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel

from voxtrama.config.settings import get_settings
from voxtrama.workflow.custom_limit import ensure_room_for
from voxtrama.workflow.document import DocumentError, read_document


class DocumentWriteError(Exception):
    """A document did not survive its own round-trip, so it was never saved.

    "if the round-trip does not come back, do not save".
    Raised before os.replace is ever called, so the file this write was
    about to replace is exactly what it was before the call.
    """


def save_document(folder: str, name: str, document: BaseModel) -> Path:
    """Write `document` to <data_dir>/`folder`/`name`.yaml, or not at all.

    Always the data directory (the user root), never the package's
    own copy: modifying a system document means writing a covering copy
    here, the same precedence document_roots already applies to reads.
    Building on data_dir alone, and never on document_roots, is what keeps
    this out of the package root even when it is writable: the path is
    never constructed, not merely rejected once built.

    mkstemp + os.replace, the same mechanism as manifest/writer.py and
    engine/progress_file.py. Unlike those two this also reads the temporary file
    back and validates it before the replace: a manifest is only ever
    regenerated from the database, but a hand-edited document has nothing
    else to regenerate it from, so a bad write has to be caught before it
    lands, not after.
    """
    if folder == "workflows":
        ensure_room_for(name)  # The edition's custom-workflow limit
    target = get_settings().data_dir / folder / f"{name}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    # allow_unicode=True is not a stylistic choice: without it safe_dump
    # escapes every non-ASCII character (\xE8 instead of è), and the file
    # stops being something a person can open and edit.
    payload = yaml.safe_dump(document.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
    handle, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    temp_path = Path(temporary)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        _verify_round_trip(temp_path, document)
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return target


def _verify_round_trip(temporary: Path, document: BaseModel) -> None:
    """Re-read `temporary` through read_document and compare it to `document`.

    Through read_document, not a second yaml.safe_load: the guarantee this
    gives is that whatever reads the file back the normal way gets
    `document`, not merely that the bytes happen to parse.
    """
    try:
        reread = read_document(temporary, type(document))
    except DocumentError as exc:
        raise DocumentWriteError(f"{temporary}: does not read back: {exc}") from exc
    if reread != document:
        raise DocumentWriteError(f"{temporary}: round-trip did not match what was written")
