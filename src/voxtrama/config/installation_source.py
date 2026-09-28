"""A pydantic-settings source that reads voxtrama.toml, the guided setup's
output file (setup.installation), so config.settings can see it
without importing voxtrama.setup. That would create a cycle:
setup.generative_step already imports voxtrama.config.settings.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from voxtrama.config.paths import default_data_dir, installation_config_path, proposal_path


class InstallationConfigSource(PydanticBaseSettingsSource):
    """Reads voxtrama.toml as a settings source, below env and dotenv.

    Only keys that are also field names on the settings class are
    returned. `Settings.model_config` has `extra="forbid"`, and
    `InstallationConfig` (setup.installation) carries fields `Settings`
    does not have yet (`instance_token` and `model_context_limits`), and
    either would otherwise make construction fail outright.
    `hardware_profile`, `ollama_model`, `ollama_url`, `cores_per_chunk`
    and `parallel_chunks` all flow through as-is, and the last three
    arrived without a line changing here when `ollama_url` and the two
    chunking fields were added to `Settings`. That is why this filters on
    field names instead of listing them one by one.

    Not read through `setup.installation.read_installation_config`:
    besides the import cycle in this module's docstring,
    `InstallationConfig` requires `cores_per_chunk`/`parallel_chunks`, so
    a hand-written file carrying only `ollama_model` would be rejected
    whole and lose the one field it exists to deliver.

    With no voxtrama.toml yet, proposal.toml stands in: the
    machine's proposal, written by setup.proposal, declared on the home
    page, replaced by voxtrama.toml once the first job has run.

    `data_dir` itself is always excluded, even though it is a field name:
    the file lives *inside* the data directory, so a value read from it
    could never be honoured to locate that same directory.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
    ) -> None:
        super().__init__(settings_cls)
        self._data_dir = self._resolve_data_dir(init_settings, env_settings, dotenv_settings)

    @staticmethod
    def _resolve_data_dir(*sources: PydanticBaseSettingsSource) -> Path:
        """`data_dir`, deferring to the strongest source that names one.

        Each source's `__call__` already returns a dict of field name
        to value, so reading `data_dir` off it needs nothing beyond
        calling it, in the same init > env > dotenv order the sources are
        tried in everywhere else.
        """
        for source in sources:
            value = source().get("data_dir")
            if value is not None:
                return Path(value)
        return default_data_dir()

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        # Nothing calls this: __call__ is overridden wholesale below,
        # following the convention InitSettingsSource uses upstream.
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        for path in (installation_config_path(self._data_dir), proposal_path(self._data_dir)):
            try:
                raw = tomllib.loads(path.read_text())
                break
            except (OSError, tomllib.TOMLDecodeError):
                continue  # absent, unreadable, or malformed: same as no file
        else:
            return {}
        return {
            key: value
            for key, value in raw.items()
            if key != "data_dir" and key in self.settings_cls.model_fields
        }
