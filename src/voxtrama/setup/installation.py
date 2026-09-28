"""The installation's configuration file.

Configuration lives in a file that can be versioned, copied between
machines and put in an infrastructure repository. The guided setup does not
change that property. This is the file the guided setup produces: one
document in the data directory, never looked up by name across two roots
like workflow.document's domain documents. It is the *outcome* of a wizard,
not something shipped with the package.

**TOML, not YAML**: the design fixes the format (the setup summary
reads "Saved to ~/Voxtrama/voxtrama.toml"). Read with the standard
library's `tomllib`, written with this module's own serializer, since
tomllib is read-only and adding a dependency for a six-field, one-table
document is not worth it.

Nothing here decides a value: a caller with no config yet gets None from
read_installation_config and has to say what a first run's defaults are
(setup.profile_offers, tuning.chunk_tuning), the same separation
diagnostics.advice keeps between measuring and deciding.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Moved to config.paths (config.settings needs them and cannot import
# this module); re-exported here under their original names.
from voxtrama.config.paths import INSTALLATION_CONFIG_FILENAME as CONFIG_FILENAME
from voxtrama.config.paths import installation_config_path
from voxtrama.config.settings import get_settings

__all__ = [
    "CONFIG_FILENAME",
    "InstallationConfig",
    "installation_config_path",
    "is_first_run",
    "read_installation_config",
    "write_installation_config",
]

HEADER = (
    "# Voxtrama installation settings. Produced by the guided setup,\n"
    "# safe to edit by hand, safe to copy to another machine. Removing this\n"
    "# file makes Voxtrama treat the next visit as a first run.\n\n"
)


class InstallationConfig(BaseModel):
    """Everything the guided setup fixes for this installation.

    Personal identity is not here: it lives on the local User row, not
    in a second model of the same person. See this package's docstring.
    """

    model_config = ConfigDict(extra="forbid")

    hardware_profile: Literal["low", "base", "high"] = "base"
    cores_per_chunk: int = Field(ge=1)
    parallel_chunks: int = Field(ge=1)
    # The num_ctx ceiling fixed per model at setup time.
    # From here on it can only be lowered, never by this file itself.
    model_context_limits: dict[str, int] = Field(default_factory=dict)
    ollama_model: str | None = None
    # The address that answered at setup time: configured, or
    # generative_step.DEFAULT_OLLAMA_URL when the step 3 probe found it
    # (setup.generative_step.effective_ollama_url). Needed because
    # providers.selection.text_provider_for reads only Settings.ollama_url.
    # Without this field, an installation configured only by the guided
    # setup could pick a model on step 4 and still fail every later run,
    # missing the address step 3 already proved.
    ollama_url: str | None = None
    # Generated once, written here, shown as a URL or QR only if remote
    # access is chosen. None until that step runs.
    instance_token: str | None = None
    # Days a finished job's data stays; None keeps it.
    retention_days: int | None = Field(default=None, ge=1, le=36500)


def is_first_run(data_dir: Path) -> bool:
    """True when no installation config exists yet."""
    return not installation_config_path(data_dir).is_file()


def read_installation_config(data_dir: Path) -> InstallationConfig | None:
    """The stored configuration, or None on a first run / an unreadable file.

    Malformed TOML or a value pydantic rejects both come back as None, the
    like a file that does not exist: whoever calls this always has a
    fallback to build from (setup.profile_offers, tuning.chunk_tuning), and
    treating a broken file as absent is a smaller fault than a first run
    that trips over its own not-yet-written config.
    """
    path = installation_config_path(data_dir)
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return None
    try:
        return InstallationConfig.model_validate(raw)
    except ValidationError:
        return None


def write_installation_config(data_dir: Path, config: InstallationConfig) -> None:
    """Write `config` as readable TOML, creating the data directory if needed.

    `get_settings` is `lru_cache`d, and this file is now one of its
    sources (config.installation_source). A process that built its Settings
    before the guided setup ran (the web process on a first visit) would
    keep serving the pre-setup values until it restarted, so whoever writes
    the file drops the cached reading of it. The worker is a different
    process and clears its own at the start of each job (worker.tasks).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    installation_config_path(data_dir).write_text(HEADER + _to_toml(config))
    get_settings.cache_clear()


def _to_toml(config: InstallationConfig) -> str:
    """A minimal TOML rendering of `config`: its five fields, nothing general.

    Not a general-purpose serializer: `json.dumps` escapes a string the way
    a TOML basic string requires for every character this schema can hold,
    which is all the generality this needs.
    """
    lines = [
        f"hardware_profile = {json.dumps(config.hardware_profile)}",
        f"cores_per_chunk = {config.cores_per_chunk}",
        f"parallel_chunks = {config.parallel_chunks}",
    ]
    if config.ollama_model is not None:
        lines.append(f"ollama_model = {json.dumps(config.ollama_model)}")
    if config.ollama_url is not None:
        lines.append(f"ollama_url = {json.dumps(config.ollama_url)}")
    if config.retention_days is not None:
        lines.append(f"retention_days = {config.retention_days}")
    if config.instance_token is not None:
        lines.append(f"instance_token = {json.dumps(config.instance_token)}")
    if config.model_context_limits:
        lines.append("\n[model_context_limits]")
        lines.extend(
            f"{json.dumps(model)} = {limit}" for model, limit in config.model_context_limits.items()
        )
    return "\n".join(lines) + "\n"
