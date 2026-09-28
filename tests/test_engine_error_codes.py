"""engine.validation.error_code_for: the codes a failed job's banner acts on."""

from __future__ import annotations

from voxtrama.engine.generative import OllamaModelNotConfiguredError
from voxtrama.engine.validation import error_code_for
from voxtrama.providers.base import ProviderTimeoutError, ProviderTransportError
from voxtrama.queue.errors import JobTimeoutError


def test_a_model_server_that_never_answered_is_unreachable_not_internal() -> None:
    assert (
        error_code_for(ProviderTransportError("connection refused"))
        == "generative_model_unreachable"
    )


def test_a_job_stopped_for_time_is_named() -> None:
    assert error_code_for(JobTimeoutError("job timed out after 186s")) == "job_timeout"


def test_the_codes_that_were_already_named_keep_their_names() -> None:
    assert error_code_for(ProviderTimeoutError("slow")) == "provider_timeout"
    assert (
        error_code_for(OllamaModelNotConfiguredError("none")) == "generative_model_not_configured"
    )
    assert error_code_for(MemoryError()) == "memory_exhausted"
    assert error_code_for(RuntimeError("boom")) == "internal"
