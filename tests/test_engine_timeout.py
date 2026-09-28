"""Tests for voxtrama.engine.timeout: the job_timeout budget itself."""

from __future__ import annotations

from voxtrama.engine.timeout import (
    MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND,
    compute_job_timeout,
)


def test_missing_bytes_grow_the_timeout() -> None:
    """A run that still has to download weights gets more time, not the same."""
    without_download = compute_job_timeout(60.0, "base")
    with_download = compute_job_timeout(60.0, "base", missing_download_bytes=500 * 1024 * 1024)

    assert with_download > without_download


def test_no_missing_bytes_is_the_same_as_not_passing_any() -> None:
    """Cached weights cost nothing: the explicit zero and the default agree."""
    assert compute_job_timeout(60.0, "base", missing_download_bytes=0) == compute_job_timeout(
        60.0, "base"
    )


def test_the_download_allowance_follows_the_minimum_bandwidth() -> None:
    """The extra grant is (roughly) the missing bytes at the floor bandwidth.

    "Roughly" because compute_job_timeout adds it before a single ceil()
    over the whole sum, not because the formula itself is approximate.
    """
    missing = 300 * 1024 * 1024
    baseline = compute_job_timeout(60.0, "base")
    grown = compute_job_timeout(60.0, "base", missing_download_bytes=missing)

    expected_allowance = missing / MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND
    assert abs((grown - baseline) - expected_allowance) < 1
