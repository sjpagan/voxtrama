"""The run's own copy of the workflow it ran.

manifest.workflow.definition_sha256 (manifest/sections.py) is a hash, not a
text: it lets a reader notice the catalogue file has changed, but says
nothing about what the run saw. That text is kept too, as a copy inside
the run. This is where
it is written and read back.

Not a field of Manifest: manifest/comparison/walk.py diffs two manifests
field by field, and the whole definition sitting inside one would turn
into an unnamed tree of differences instead of the single
definition_sha256 line a reader already gets. And Manifest is
`extra="forbid"` (manifest/schema.py), so a new field there breaks an old
reader (run artefacts already live as files in the run's own
folder, which is where this one goes instead).

Kept next to sections.py's hashing rather than duplicating it: both read
`workflow_definition_payload`, so the copy on disk and the hash in the
manifest can never describe two different serializations of the same
workflow.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from voxtrama.manifest.jsonfile import write_atomic
from voxtrama.workflow.definition import Workflow

WORKFLOW_COPY_FILENAME = "workflow.json"

logger = logging.getLogger(__name__)


def workflow_copy_path(runs_dir: Path, run_id: str) -> Path:
    """The workflow copy of `run_id`, inside that run's own folder."""
    return runs_dir / run_id / WORKFLOW_COPY_FILENAME


def workflow_definition_payload(workflow: Workflow) -> dict[str, Any]:
    """The canonical dict form of a workflow's definition.

    The one payload both definition_sha256 and the on-disk copy are built
    from. See the module docstring for why they must not diverge.
    """
    return workflow.model_dump(mode="json")


def workflow_definition_sha256(workflow: Workflow) -> str:
    """sha256 of `workflow_definition_payload`, sorted and compact.

    Moved here from manifest/sections.py's workflow_info, which now calls
    this instead of serializing the definition itself.
    """
    payload = json.dumps(
        workflow_definition_payload(workflow), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_workflow_copy(runs_dir: Path, run_id: str, workflow: Workflow) -> None:
    """Write `run_id`'s workflow copy, once.

    A run's definition does not change mid-run, and write_run_manifest
    calls this on every manifest rewrite (each step, each retry): writing
    again would only add work, and an atomic replace of an unchanged file
    is not free just because the bytes end up the same. So this is a
    no-op once the file exists.

    This function trusts its caller entirely: it has no way to tell a
    `workflow` a run executed from one merely reloaded from the
    catalogue after the fact. Writing the latter as `run_id`'s copy would
    attest to something false, which this copy exists to prevent. That
    judgement is write_run_manifest's own `workflow_from_run`, not this
    function's. Do not call this directly from a process that only
    reloaded a definition (engine.reconcile_close is the one caller that
    must not).

    Tolerates OSError like write_run_manifest does, for the same reason: a
    run that is otherwise going well must not fail because this file could
    not be written.
    """
    path = workflow_copy_path(runs_dir, run_id)
    if path.is_file():
        return
    try:
        write_atomic(workflow_definition_payload(workflow), path)
    except OSError:
        logger.warning("could not write workflow copy")


def read_workflow_copy(runs_dir: Path, run_id: str) -> Workflow | None:
    """Read `run_id`'s workflow copy, or None if it is missing or unreadable.

    Not `load_workflow` (workflow/loader.py): that revalidates skill and
    version references against BUILTIN_SKILLS, which is wrong here: a run
    whose skill has since been removed from the catalogue must
    still be readable back, since it is a record of what already ran, not
    a proposal to run again. `Workflow.model_validate` alone checks only
    the shape.

    Tolerant of a missing or corrupt file the same way
    engine.reconcile_manifest.reloaded_workflow and
    engine.superseded._reloaded_workflow already tolerate a catalogue entry
    that is gone: an exception here must never reach a caller, only a
    warning and None.
    """
    path = workflow_copy_path(runs_dir, run_id)
    if not path.is_file():
        return None
    try:
        return Workflow.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        logger.warning("could not read workflow copy for run %r", run_id)
        return None
