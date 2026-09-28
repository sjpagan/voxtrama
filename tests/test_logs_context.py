"""Tests for voxtrama.logs.context."""

from __future__ import annotations

import pytest

from voxtrama.logs.context import current_context, log_context


def test_no_context_by_default() -> None:
    assert current_context() == {}


def test_log_context_sets_given_fields() -> None:
    with log_context(run_id="r_7f3a", step="transcribe"):
        assert current_context() == {"run_id": "r_7f3a", "step": "transcribe"}
    assert current_context() == {}


def test_log_context_nests_without_losing_the_outer_run_id() -> None:
    with log_context(run_id="r_7f3a"):
        assert current_context() == {"run_id": "r_7f3a"}
        with log_context(step="transcribe"):
            assert current_context() == {"run_id": "r_7f3a", "step": "transcribe"}
        assert current_context() == {"run_id": "r_7f3a"}
    assert current_context() == {}


def test_log_context_restores_previous_state_on_exception() -> None:
    with log_context(run_id="r_7f3a"):
        with pytest.raises(ValueError):
            with log_context(step="transcribe"):
                raise ValueError("boom")
        assert current_context() == {"run_id": "r_7f3a"}
    assert current_context() == {}
