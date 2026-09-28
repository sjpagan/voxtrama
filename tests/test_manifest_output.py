"""write_run_output and read_run_output against a bare runs_dir.

Driving output.json through execute_run end to end is covered by
tests/test_engine_output.py. This file is only about the two functions
themselves: the shape, the digest, and what read_run_output does with a
run that never wrote one, or a file that is there but corrupt.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from voxtrama.manifest.output import output_path, read_run_output, write_run_output


def test_output_lives_in_the_run_own_folder(tmp_path):
    """A run is a folder you can open, while it runs and after."""
    write_run_output(tmp_path, "r1", {})

    assert output_path(tmp_path, "r1").parent.name == "r1"


def test_an_empty_produced_dict_is_still_written(tmp_path):
    """A run with nothing produced yet reports that, not an absent file."""
    write_run_output(tmp_path, "r1", {})

    payload = json.loads(output_path(tmp_path, "r1").read_bytes())
    assert payload == {"output_version": 1, "run_id": "r1", "steps": {}}


def test_the_returned_digest_matches_the_bytes_on_disk(tmp_path):
    digest = write_run_output(tmp_path, "r1", {"transcribe": {"language": "en"}})

    on_disk = output_path(tmp_path, "r1").read_bytes()
    assert digest == hashlib.sha256(on_disk).hexdigest()


def test_read_run_output_returns_none_for_a_run_that_never_wrote_one(tmp_path):
    assert read_run_output(tmp_path, "no-such-run") is None


def test_read_run_output_raises_on_a_corrupt_file(tmp_path):
    path = output_path(tmp_path, "r1")
    path.parent.mkdir(parents=True)
    path.write_text("not json")

    with pytest.raises(ValidationError):
        read_run_output(tmp_path, "r1")
