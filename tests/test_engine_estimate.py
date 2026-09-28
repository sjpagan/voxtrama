"""The honest estimate, told apart from the generous budget."""

from __future__ import annotations

import pytest

from voxtrama.engine.estimate import estimate_download_seconds, estimate_processing_seconds
from voxtrama.engine.timeout import MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND, compute_job_timeout

ONE_MINUTE = 60.0


def test_the_estimate_is_lower_than_the_budget_that_kills_the_job() -> None:
    """Quoting the timeout to a person would promise 86 minutes for a 56-minute run."""
    estimate = estimate_processing_seconds(ONE_MINUTE, "base")
    budget = compute_job_timeout(ONE_MINUTE, "base")

    assert estimate < budget


def test_a_heavier_profile_is_expected_to_take_longer() -> None:
    assert estimate_processing_seconds(ONE_MINUTE, "high") > estimate_processing_seconds(
        ONE_MINUTE, "base"
    )
    assert estimate_processing_seconds(ONE_MINUTE, "low") < estimate_processing_seconds(
        ONE_MINUTE, "base"
    )


def test_the_estimate_scales_with_the_audio() -> None:
    one = estimate_processing_seconds(ONE_MINUTE, "base")
    ten = estimate_processing_seconds(ONE_MINUTE * 10, "base")

    assert ten == pytest.approx(one * 10)


def test_download_time_uses_the_same_floor_bandwidth_as_the_budget() -> None:
    """One number in two places would drift. The floor is shared on purpose."""
    seconds = estimate_download_seconds(MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND * 60)

    assert seconds == 60


def test_nothing_to_download_costs_nothing() -> None:
    assert estimate_download_seconds(0) == 0
