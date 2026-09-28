"""Tests for rendering.run_failure.failure_banner_view."""

from __future__ import annotations

from voxtrama.rendering.run_failure import MemoryFacts, failure_banner_view

_MEMORY = MemoryFacts(
    used_parallel_chunks=2,
    used_cores_per_chunk=4,
    recommended_parallel_chunks=4,
    recommended_cores_per_chunk=2,
    notice="This machine has 8 GiB; 16 GiB is recommended.",
)


def _banner(code: str, raw_error: str | None = "boom"):
    return failure_banner_view(
        code,
        raw_error,
        _MEMORY,
        model_settings_href="/setup/model-ready",
        processing_settings_href="/setup/local-processing",
        retry_href="/runs/run-1/retry",
    )


def test_no_generative_model_points_at_the_model_settings_page() -> None:
    banner = _banner("generative_model_not_configured")

    assert banner.title_key == "generative_model_not_configured"
    assert banner.memory is None
    hrefs = [action.href for action in banner.actions]
    assert "/setup/model-ready" in hrefs
    assert "/runs/run-1/retry" in hrefs


def test_memory_exhausted_carries_the_used_and_recommended_values() -> None:
    banner = _banner("memory_exhausted")

    assert banner.title_key == "memory_exhausted"
    assert banner.memory == _MEMORY
    hrefs = [action.href for action in banner.actions]
    assert "/setup/local-processing" in hrefs


def test_interrupted_is_treated_as_a_memory_symptom_too() -> None:
    """A worker that vanished mid-step is one of the three named
    symptoms of a memory failure, hedged rather than asserted in the
    banner's own wording. The numbers are shown regardless."""
    banner = _banner("interrupted")

    assert banner.title_key == "interrupted"
    assert banner.memory == _MEMORY


def test_an_unknown_code_shows_the_raw_error_instead_of_inventing_one() -> None:
    banner = _banner("some_future_code", raw_error="a message nobody classified yet")

    assert banner.title_key is None
    assert banner.message == "a message nobody classified yet"
    assert banner.memory is None
    assert [action.key for action in banner.actions] == ["retry"]


def test_an_unreachable_summary_model_points_at_the_model_settings_page() -> None:
    """«No summary model reachable», Open settings, Retry."""
    banner = _banner("generative_model_unreachable")

    assert banner.title_key == "generative_model_unreachable"
    assert [action.key for action in banner.actions] == ["open_settings", "retry"]
    assert banner.actions[0].href == "/setup/model-ready"


def test_a_job_out_of_time_keeps_the_reason_beside_its_title() -> None:
    banner = _banner("job_timeout", "job timed out after 186s, granted for 58s of audio")

    assert banner.title_key == "job_timeout"
    assert banner.message == "job timed out after 186s, granted for 58s of audio"
    assert [action.key for action in banner.actions] == ["retry"]
