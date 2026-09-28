"""Whether the three status cards can back up what they claim."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.advice import COMFORTABLE_FREE_DISK_BYTES
from voxtrama.diagnostics.readiness import Readiness, check_private_storage, read_readiness


@pytest.fixture
def uncached(monkeypatch):
    """Nothing on disk: the profile's model has never been downloaded."""
    monkeypatch.setattr(
        "voxtrama.diagnostics.readiness_models.is_cached", lambda weights, models_dir: False
    )


@pytest.fixture
def cached(monkeypatch):
    monkeypatch.setattr(
        "voxtrama.diagnostics.readiness_models.is_cached", lambda weights, models_dir: True
    )


def test_local_processing_is_ready_when_the_configured_profile_resolves(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, hardware_profile="base")

    check = read_readiness(settings).local_processing

    assert check.state is Readiness.READY
    assert "base" in check.reason


def test_models_ready_names_the_missing_model_on_a_fresh_install(uncached, tmp_path: Path) -> None:
    """The case that counts: no model downloaded yet must not say 'ready'."""
    settings = Settings(data_dir=tmp_path, hardware_profile="base")

    check = read_readiness(settings).models_ready

    assert check.state is Readiness.NOT_READY
    assert check.model == "medium"
    assert "medium" in check.reason


def test_models_ready_follows_the_profile_to_the_right_model_name(uncached, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, hardware_profile="high")

    check = read_readiness(settings).models_ready

    assert check.model == "large-v3"
    assert "large-v3" in check.reason


def test_models_ready_is_ready_once_the_weights_are_cached(cached, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, hardware_profile="low")

    check = read_readiness(settings).models_ready

    assert check.state is Readiness.READY
    assert check.model == "small"


def test_private_storage_is_ready_on_a_writable_directory_with_room(tmp_path: Path) -> None:
    check = check_private_storage(Settings(data_dir=tmp_path))

    assert check.state is Readiness.READY
    assert check.free_disk_bytes is not None and check.free_disk_bytes > 0


def test_private_storage_is_not_ready_when_the_directory_is_missing(tmp_path: Path) -> None:
    check = check_private_storage(Settings(data_dir=tmp_path / "nowhere"))

    assert check.state is Readiness.NOT_READY
    assert "does not exist" in check.reason


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the permission bits this asserts on",
)
def test_private_storage_is_not_ready_when_the_directory_refuses_a_write(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        check = check_private_storage(Settings(data_dir=locked))
    finally:
        locked.chmod(0o700)

    assert check.state is Readiness.NOT_READY
    assert "not writable" in check.reason


def test_private_storage_is_not_ready_when_space_is_short(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "voxtrama.diagnostics.readiness_storage.read_free_disk_bytes",
        lambda path: COMFORTABLE_FREE_DISK_BYTES - 1,
    )

    check = check_private_storage(Settings(data_dir=tmp_path))

    assert check.state is Readiness.NOT_READY
    assert "GiB free" in check.reason


def test_private_storage_is_unknown_when_free_space_cannot_be_read(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "voxtrama.diagnostics.readiness_storage.read_free_disk_bytes", lambda path: None
    )

    check = check_private_storage(Settings(data_dir=tmp_path))

    assert check.state is Readiness.UNKNOWN


def test_read_readiness_reports_all_three(uncached, tmp_path: Path) -> None:
    report = read_readiness(Settings(data_dir=tmp_path))

    assert report.local_processing.state is Readiness.READY
    assert report.models_ready.state is Readiness.NOT_READY
    assert report.private_storage.state is Readiness.READY
