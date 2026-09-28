"""Tests for voxtrama.config.settings.

The installation-file source has its own test module,
test_settings_installation_source.py, to stay under the project's 150-line
file cap.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from voxtrama.config.settings import (
    Settings,
    _missing_env_message,
    get_settings,
)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOXTRAMA_QUEUE_URL", "redis://localhost:6379/0")
    settings = Settings()
    assert settings.profile == "local"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.ollama_url is None
    assert settings.ollama_auth is None
    assert settings.provider_timeout_seconds == 1800
    assert settings.models_dir == settings.data_dir / "models"
    assert settings.database_url == f"sqlite:///{settings.data_dir / 'voxtrama.db'}"
    # None means "nobody decided yet", never a constant
    # chosen because it is low, which is what transcription.
    # resources.resolve_engine_resources falls back to instead.
    assert settings.cores_per_chunk is None
    assert settings.parallel_chunks is None


def test_ollama_auth_never_shows_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """The credential is a secret, and repr(settings) must say so."""
    monkeypatch.setenv("VOXTRAMA_QUEUE_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("VOXTRAMA_OLLAMA_AUTH", "a-very-real-token")

    settings = Settings()

    assert "a-very-real-token" not in repr(settings)
    assert settings.ollama_auth.get_secret_value() == "a-very-real-token"


def test_a_required_variable_still_fails_with_its_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No variable is mandatory today, but the rule that covers them is.

    A variable that cannot have a default must fail at startup
    saying what is missing, not with a raw pydantic traceback. With every
    field now defaulted, that machinery would never run, and untested
    machinery stops working without anyone noticing.
    """

    class WithRequired(Settings):
        mandatory_thing: str

    monkeypatch.delenv("VOXTRAMA_MANDATORY_THING", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        WithRequired()

    assert "VOXTRAMA_MANDATORY_THING" in _missing_env_message(excinfo.value)


def test_queue_url_falls_back_to_the_documented_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No decision is required before the first success.

    Without a default the very first command a user runs fails on a variable
    nobody told them to set. With one, a missing Redis fails as a connection
    error instead, which at least says what is not answering.
    """
    monkeypatch.delenv("VOXTRAMA_QUEUE_URL", raising=False)
    get_settings.cache_clear()

    assert get_settings().queue_url == "redis://localhost:6379/0"
