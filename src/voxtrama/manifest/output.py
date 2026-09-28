"""The shape and the writing of a run's own output.json.

manifest never imports engine (see manifest/evidence.py's docstring and
tests/test_architecture.py): this file takes ExecutionContext.produced as a
plain dict, not the dataclass it lives in, so this layer stays reachable
from anywhere the manifest already is.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from voxtrama.manifest.jsonfile import serialize, write_atomic

OUTPUT_FILENAME = "output.json"
OUTPUT_VERSION: Literal[1] = 1

logger = logging.getLogger(__name__)


class RunOutput(BaseModel):
    """What every step of a run produced, keyed by step_id.

    Not a flat namespace, for the same reason ExecutionContext.produced
    isn't one: two steps that happen to name the same field must not be
    able to overwrite each other's result.
    """

    model_config = ConfigDict(extra="forbid")
    output_version: Literal[1] = OUTPUT_VERSION
    run_id: str
    steps: dict[str, dict[str, Any]]


def output_path(runs_dir: Path, run_id: str) -> Path:
    """The output.json of `run_id`, inside that run's own folder."""
    return runs_dir / run_id / OUTPUT_FILENAME


def write_run_output(
    runs_dir: Path, run_id: str, produced: dict[str, dict[str, Any]]
) -> str | None:
    """Write `produced` to disk and return the sha256 of the bytes just written.

    Written unconditionally, even when `produced` is empty: a run that has
    not produced anything yet is still a truth the manifest keeps readable while
    the run goes, not an absence to special-case away.

    Tolerates OSError like write_run_manifest does, for the same reason: a
    run that is otherwise going well must not fail because this file could
    not be written. Returns None in that case, and callers must not treat
    None as "nothing to hash": it means the write itself did not happen.
    """
    payload = RunOutput(run_id=run_id, steps=produced).model_dump(mode="json")
    try:
        data = write_atomic(payload, output_path(runs_dir, run_id))
    except OSError:
        logger.warning("could not write run output")
        return None
    return hashlib.sha256(data).hexdigest()


def step_output_hash(step_id: str, produced: dict[str, dict[str, Any]] | None) -> str | None:
    """The sha256 of what `step_id` produced, hashed the same way output.json is written.

    Public, moved here from manifest/step_info.py: the same value
    written as steps[].output_sha256 is also one of the ingredients
    engine.step_hashing.input_sha256 folds into a dependent step's own
    hash, so both read this one function rather than risking two
    serializations of the same dict drifting apart.

    Reads `jsonfile.serialize` on purpose: hashing a different
    serialization of the same dict would make this hash change from run to
    run for no reason a reader could see. None when `step_id` produced
    nothing (skipped, or failed before producing), never an empty string.
    """
    if produced is None or step_id not in produced:
        return None
    return hashlib.sha256(serialize(produced[step_id])).hexdigest()


def read_run_output(runs_dir: Path, run_id: str) -> RunOutput | None:
    """Read the output.json of `run_id`, or None if the run has not written one yet.

    A file that exists but is corrupt or fails validation is not the same
    as an absent one: that exception is left to rise rather than folded
    into None, because a caller must be able to tell "not produced yet"
    from "something is wrong with what is on disk".
    """
    path = output_path(runs_dir, run_id)
    if not path.is_file():
        return None
    return RunOutput.model_validate_json(path.read_bytes())
