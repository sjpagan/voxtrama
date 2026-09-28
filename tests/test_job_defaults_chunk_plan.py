"""The new-job form keeps cores per chunk and parallel chunks apart.

transcription.resources folds the two into one thread count, because one
transcribe() call is all there is to feed. The form is a different
question: it shows the two numbers the person set, and POST /jobs compares
a submission against them. Reading the folded value here would show the
product as "cores per chunk" and 1 as "parallel chunks", so a form on an
installation set to 4 and 2 would claim 8 and 1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.machine import machine_with_cores

from voxtrama.api.routes.job_defaults import job_defaults
from voxtrama.config.settings import Settings


def _twenty_cores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patched on the route module: it binds read_machine by name at import."""
    monkeypatch.setattr(
        "voxtrama.api.routes.job_defaults.read_machine",
        lambda data_dir=None: machine_with_cores(20),
    )


def test_the_form_shows_the_two_numbers_the_installation_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _twenty_cores(monkeypatch)

    defaults = job_defaults(Settings(data_dir=tmp_path, cores_per_chunk=4, parallel_chunks=2))

    assert (defaults.cores_per_chunk, defaults.parallel_chunks) == (4, 2)


def test_a_number_beyond_the_machine_is_capped_at_what_it_has(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _twenty_cores(monkeypatch)

    defaults = job_defaults(Settings(data_dir=tmp_path, cores_per_chunk=64, parallel_chunks=2))

    assert defaults.cores_per_chunk == 20
    assert defaults.parallel_chunks == 2
