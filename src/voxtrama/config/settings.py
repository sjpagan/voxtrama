"""Application configuration, read from the environment and, below it
(see `settings_customise_sources`), from the guided setup's output file
(config.installation_source).

Every variable is prefixed VOXTRAMA_ and has a working default. A value
that fails validation is a startup error, not a runtime surprise, and the
error names the variable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from voxtrama.config.installation_source import InstallationConfigSource
from voxtrama.config.paths import default_data_dir, get_paths
from voxtrama.config.providers import ProviderConfig, ProviderUrl


class SettingsError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    """Runtime configuration shared by every Voxtrama entrypoint."""

    model_config = SettingsConfigDict(env_prefix="VOXTRAMA_", hide_input_in_errors=True)

    data_dir: Path = Field(default_factory=default_data_dir)
    # Inside the container `data_dir` is always `/data`. compose.yaml
    # passes the host-side folder here, so the setup pages can show it.
    # None means it is not known (outside the compose file this repo ships).
    host_data_dir: str | None = None
    # The Host names a request may carry. Any other
    # is refused, which stops DNS rebinding (api.security).
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "::1"]
    models_dir: Path | None = None
    # The private material `voxtrama calibrate` reads: real
    # recordings, never shipped with Voxtrama. No default:
    # whoever has not built this material yet must not fail on start-up
    # over it. calibrate treats unset as its first, honest case instead of
    # guessing a path that is never there.
    eval_dir: Path | None = None
    database_url: str | None = None
    # A default, so the first command a user runs does not fail on
    # a variable nobody told them to set. If Redis is not there the failure is
    # a connection error, which says what is not answering: one step further
    # along than a configuration error.
    queue_url: str = "redis://localhost:6379/0"
    profile: Literal["local", "server"] = "local"
    # Chosen, never detected. A guess that is wrong for the
    # machine degrades quality without saying so. An explicit default that
    # a user can override does not.
    hardware_profile: Literal["low", "base", "high"] = "base"
    # faster-whisper's cpu_threads/num_workers, which nothing read
    # before this. None, same reason as hardware_profile above: the tuning
    # fallback in transcription.resources proposes a real number, never a
    # constant guessed here. The guided setup writes both to voxtrama.toml.
    cores_per_chunk: int | None = None
    parallel_chunks: int | None = None
    # The ceiling diarisation may report. A parameter with a default,
    # not a module constant baked into diarization/assign.py. Whether a
    # fixed ceiling should exist at all is a separate, still-open question.
    max_speakers: int = 4
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    ollama_url: ProviderUrl | None = None
    # A secret, never a str (SecretStr's repr is "**********").
    ollama_auth: SecretStr | None = None
    # The providers a run can name (VOXTRAMA_PROVIDERS, JSON). When
    # empty, ollama_url/ollama_auth form the one called "default" (providers.registry).
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    # No default. A default here would quietly become our
    # recommendation of which model to use, which we cannot give
    # yet. engine.generative fails a step naming this variable when it is
    # missing, instead of guessing.
    ollama_model: str | None = None
    # Every step has a declared maximum time. This is the
    # value everything falls back to until Step carries its own.
    # 120 was measured to guarantee failure on real
    # content (33 CPU minutes on a 59-minute call). 1800
    # matches tuning/generic.yaml's generative.timeout_seconds.
    provider_timeout_seconds: float = 1800
    # Windows of one step sent to the model at once (engine.window_calls).
    parallel_windows: int = Field(default=2, ge=1, le=16)
    # The new-job form's defaults, each changeable per job (RunChoices).
    summary_detail: int = Field(default=3, ge=1, le=5)
    pause_merge_seconds: float = Field(default=1.5, ge=0.1, le=10.0)
    # The locale tried after Accept-Language; None skips it instead of pinning "en".
    default_locale: str | None = None
    # For security, the most one new-job upload may weigh, in MB.
    max_upload_mb: int = Field(default=8192, ge=1)
    # Days a finished job's data stays; None, the default, keeps it.
    retention_days: int | None = Field(default=None, ge=1, le=36500)

    @model_validator(mode="after")
    def _fill_derived_defaults(self) -> Settings:
        """Fill models_dir and database_url from data_dir when not set."""
        if self.models_dir is None:
            self.models_dir = self.data_dir / "models"
        if self.database_url is None:
            self.database_url = f"sqlite:///{get_paths(self.data_dir).db_path}"
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Insert the installation file below env and dotenv, above defaults.

        Precedence, strongest first: init > env > dotenv > this file >
        the field's default. A value the guided setup wrote survives until
        someone overrides it through the environment, never the other way
        around.
        """
        toml_settings = InstallationConfigSource(
            settings_cls, init_settings, env_settings, dotenv_settings
        )
        return init_settings, env_settings, dotenv_settings, toml_settings, file_secret_settings


def _missing_env_message(exc: ValidationError) -> str:
    """Turn a pydantic validation error into a message naming the variable."""
    missing = [
        f"VOXTRAMA_{error['loc'][0]}".upper()
        for error in exc.errors()
        if error["type"] == "missing"
    ]
    if missing:
        return f"Missing required environment variable(s): {', '.join(missing)}"
    return str(exc)


@lru_cache
def get_settings() -> Settings:
    """Build the process-wide Settings instance, cached after the first call."""
    try:
        return Settings()
    except ValidationError as exc:
        raise SettingsError(_missing_env_message(exc)) from exc
