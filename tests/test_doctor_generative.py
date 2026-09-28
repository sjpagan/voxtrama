"""What `voxtrama doctor` prints about generative models.

Split from test_diagnostics_generative.py: that file is about
diagnostics.generative's pure functions. This is about the sentences
cli.commands.doctor_generative prints from them, which needs typer's own
echo captured (capsys) rather than a bare Fit compared in an assert.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import voxtrama.cli.commands.doctor_generative as doctor_generative
from voxtrama.cli.commands.doctor_generative import print_generative
from voxtrama.config.settings import get_settings
from voxtrama.diagnostics.advice import GIB
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.workflow.document import DocumentNotFoundError

_ONE_HUGE_MODEL = (
    "version: 1\n"
    "models:\n"
    "  - name: too-big-for-anything\n"
    "    parameters_b: 900.0\n"
    "    quantization: q4_K_M\n"
    "    required_memory_gib: 4000.0\n"
)

_ONE_SMALL_MODEL = (
    "version: 1\n"
    "models:\n"
    "  - name: comfortably-small\n"
    "    parameters_b: 3.0\n"
    "    quantization: q4_K_M\n"
    "    required_memory_gib: 2.0\n"
)

_MACHINE = MachineReport(
    platform="test",
    architecture="test",
    cpu_count=8,
    performance_cores=None,
    efficiency_cores=None,
    cpu_brand=None,
    total_memory_bytes=16 * GIB,
    unified_memory=False,
    free_disk_bytes=100 * GIB,
    gpu_available=False,
    accelerator=None,
    in_container=False,
)


def _point_data_dir_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, table_yaml: str) -> None:
    catalog_dir = tmp_path / "model-catalog"
    catalog_dir.mkdir()
    (catalog_dir / "generative.yaml").write_text(table_yaml)
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()


def test_when_nothing_fits_doctor_names_the_fact_and_a_remote_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The point: "nobody fits" is said outright, not softened."""
    _point_data_dir_at(tmp_path, monkeypatch, _ONE_HUGE_MODEL)

    print_generative(_MACHINE)

    output = capsys.readouterr().out
    assert "no model" in output and "fits in this machine's memory" in output
    assert "remote provider" in output


def test_when_a_model_fits_its_line_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _point_data_dir_at(tmp_path, monkeypatch, _ONE_SMALL_MODEL)

    print_generative(_MACHINE)

    output = capsys.readouterr().out
    assert "comfortably-small" in output
    assert "does not fit" not in output


def test_a_missing_table_prints_a_line_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """New behaviour for a missing table needs a test.

    `find_document` already raises DocumentNotFoundError when no root has
    the file. This checks doctor's own reaction to that, not find_document
    itself (see test_workflow_document.py).
    """

    def _raise() -> None:
        raise DocumentNotFoundError("no generative model table named 'generative' in: nowhere")

    monkeypatch.setattr(doctor_generative, "load_generative_table", _raise)

    print_generative(_MACHINE)

    output = capsys.readouterr().out
    assert "could not be read" in output
