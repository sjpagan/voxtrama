"""Whether a generative model fits this machine.

Split from test_diagnostics.py, a context of its own: this is about
diagnostics.generative's pure fit logic and the model-catalog/ document
root, not about advice.py's memory-and-disk thresholds.
test_doctor_generative.py covers a third context (what `doctor` prints)
separately again, since it needs a full CliRunner-free capture of
typer.echo instead of these bare dataclasses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.config.settings import get_settings
from voxtrama.diagnostics.advice import GIB
from voxtrama.diagnostics.generative import (
    GenerativeModel,
    GenerativeTable,
    assess_fit,
    fits,
    load_generative_table,
)
from voxtrama.diagnostics.machine import MachineReport

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


def _model(name: str, required_memory_gib: float) -> GenerativeModel:
    return GenerativeModel(
        name=name, parameters_b=7.0, quantization="q4_K_M", required_memory_gib=required_memory_gib
    )


def test_a_model_with_room_to_spare_fits_and_reports_a_positive_margin() -> None:
    result = fits(_model("small", required_memory_gib=4.0), _MACHINE)

    assert result.fits
    assert result.margin_bytes is not None and result.margin_bytes > 0


def test_a_model_too_big_does_not_fit_and_reports_a_negative_margin() -> None:
    result = fits(_model("huge", required_memory_gib=64.0), _MACHINE)

    assert not result.fits
    assert result.margin_bytes is not None and result.margin_bytes < 0


def test_fitting_exactly_does_not_fit_once_the_reserve_is_subtracted() -> None:
    """Exact fit means it does not fit: the OS and Voxtrama run here too."""
    required_gib = _MACHINE.total_memory_bytes / GIB  # type: ignore[operator]
    result = fits(_model("exact", required_memory_gib=required_gib), _MACHINE)

    assert not result.fits


def test_an_unread_memory_declares_no_model_fit_without_a_zero_margin() -> None:
    unknown = MachineReport(
        platform="test",
        architecture="test",
        cpu_count=8,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand=None,
        total_memory_bytes=None,
        unified_memory=False,
        free_disk_bytes=100 * GIB,
        gpu_available=False,
        accelerator=None,
        in_container=False,
    )
    table = GenerativeTable(version=1, models=[_model("small", 4.0), _model("huge", 64.0)])

    assessed, reason = assess_fit(table, unknown)

    assert all(not one.fits for one in assessed)
    assert all(one.margin_bytes is None for one in assessed)
    assert reason is not None and "memory could not be read" in reason


def test_the_order_of_results_follows_the_file_never_the_margin() -> None:
    """A `sorted()` slipped in here would read as a quality ranking."""
    table = GenerativeTable(
        version=1,
        models=[_model("tightest", 15.9), _model("comfortable", 4.0), _model("roomiest", 1.0)],
    )

    assessed, _ = assess_fit(table, _MACHINE)

    assert [one.model.name for one in assessed] == ["tightest", "comfortable", "roomiest"]


def test_a_table_in_the_data_dir_wins_over_the_one_the_package_ships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """document_roots' own rule, inherited by this third folder."""
    override_dir = tmp_path / "model-catalog"
    override_dir.mkdir()
    (override_dir / "generative.yaml").write_text(
        "version: 1\n"
        "models:\n"
        "  - name: only-the-override-has-this-one\n"
        "    parameters_b: 1.0\n"
        "    quantization: q4_K_M\n"
        "    required_memory_gib: 1.0\n"
    )
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    table = load_generative_table()

    assert [model.name for model in table.models] == ["only-the-override-has-this-one"]
