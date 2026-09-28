"""rendering.setup_processing: the machine line and the profile/chunk views."""

from __future__ import annotations

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.rendering.setup_processing import (
    chunk_plan_view,
    machine_summary,
    profile_offer_views,
)
from voxtrama.setup.profile_offers import ProfileOffer
from voxtrama.tuning.chunk_tuning import ChunkPlan


def test_apple_silicon_reads_as_its_own_line() -> None:
    machine = MachineReport(
        platform="darwin",
        architecture="arm64",
        cpu_count=16,
        performance_cores=11,
        efficiency_cores=5,
        cpu_brand="Apple M3 Pro",
        total_memory_bytes=36 * 1024**3,
        unified_memory=True,
        free_disk_bytes=500 * 1024**3,
        gpu_available=True,
        accelerator="mps",
        in_container=False,
    )

    line = machine_summary(machine)

    assert line == "Apple M3 Pro · 11 performance cores · 5 efficiency · 36 GB unified · Metal"


def test_a_machine_with_no_unified_memory_says_ram_not_unified() -> None:
    machine = MachineReport(
        platform="linux",
        architecture="x86_64",
        cpu_count=8,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand="Generic x86_64",
        total_memory_bytes=32 * 1024**3,
        unified_memory=False,
        free_disk_bytes=100 * 1024**3,
        gpu_available=False,
        accelerator=None,
        in_container=False,
    )

    line = machine_summary(machine)

    assert "32 GB RAM" in line
    assert "unified" not in line
    assert "no accelerator" in line


def test_an_unreadable_memory_reading_says_unknown_never_a_zero() -> None:
    machine = MachineReport(
        platform="linux",
        architecture="x86_64",
        cpu_count=None,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand=None,
        total_memory_bytes=None,
        unified_memory=False,
        free_disk_bytes=None,
        gpu_available=False,
        accelerator=None,
        in_container=False,
    )

    line = machine_summary(machine)

    assert "unknown memory" in line
    assert "unknown cores" in line


def test_a_disabled_offer_shows_the_reason_with_real_byte_figures() -> None:
    offer = ProfileOffer(
        key="high",
        model_size="large-v3",
        download_bytes=3090 * 1024 * 1024,
        processing_seconds_per_hour=1000.0,
        recommended=False,
        fits_free_disk=False,
    )

    [view] = profile_offer_views([offer], free_disk_bytes=1 * 1024**3, cached_keys=set())

    assert view.available is False
    assert "1.0 GB" in view.unavailable_reason
    assert view.display_name == "Maximum accuracy"
    assert view.model_label == "whisper-large-v3"


def test_the_amber_warning_names_the_files_own_recommended_number() -> None:
    plan = ChunkPlan(cores_per_chunk=8, parallel_chunks=6, recommended_parallel_chunks=2)

    view = chunk_plan_view(plan, model_download_bytes=1024**3)

    assert view.exceeds_recommended is True
    assert view.warning == "Above the 2 chunks recommended for this machine"


def test_no_warning_when_within_the_recommendation() -> None:
    plan = ChunkPlan(cores_per_chunk=8, parallel_chunks=2, recommended_parallel_chunks=2)

    view = chunk_plan_view(plan, model_download_bytes=1024**3)

    assert view.warning is None
