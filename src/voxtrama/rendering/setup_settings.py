"""What GET /setup shows: the installation's configuration, read
from voxtrama.toml, and for each field whether the environment is the
one in force.

Settings' precedence is fixed at init > env > dotenv > voxtrama.toml
> default. A value this page's forms write can therefore have no effect
when a VOXTRAMA_* variable already names the same field. The only way
to tell is comparing what the file holds
(setup.installation.read_installation_config) with what `get_settings()`
resolved to. Equal: the file's value is in force. Different: something
above it in that order won, and that can only be an environment
variable, since nothing else in that order changes between two calls in
the same process.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.config.settings import Settings
from voxtrama.rendering.setup_processing import profile_display_name
from voxtrama.setup.installation import InstallationConfig
from voxtrama.setup.profile_offers import PROFILE_KEYS


@dataclass(frozen=True)
class ConfigFieldView:
    """One row of the summary: the file's value, formatted, and whether
    `Settings` resolved to something else (the environment won).
    """

    value: str
    from_environment: bool


@dataclass(frozen=True)
class SettingsOverviewView:
    """The four facts pages/setup_settings.html shows at the top."""

    hardware_profile: ConfigFieldView
    parallelism: ConfigFieldView
    generative_model: ConfigFieldView
    provider_address: ConfigFieldView


def settings_overview_view(config: InstallationConfig, settings: Settings) -> SettingsOverviewView:
    parallelism_value = f"{config.parallel_chunks} chunks × {config.cores_per_chunk} cores"
    parallelism_from_env = (
        config.cores_per_chunk != settings.cores_per_chunk
        or config.parallel_chunks != settings.parallel_chunks
    )
    return SettingsOverviewView(
        hardware_profile=ConfigFieldView(
            value=profile_display_name(config.hardware_profile),
            from_environment=config.hardware_profile != settings.hardware_profile,
        ),
        parallelism=ConfigFieldView(value=parallelism_value, from_environment=parallelism_from_env),
        generative_model=ConfigFieldView(
            value=config.ollama_model or "-",
            from_environment=config.ollama_model != settings.ollama_model,
        ),
        provider_address=ConfigFieldView(
            value=config.ollama_url or "-",
            from_environment=config.ollama_url != settings.ollama_url,
        ),
    )


@dataclass(frozen=True)
class ProfileOption:
    """One choice of the "Profile" select in pages/setup_settings.html.
    A dropdown, not a card: this page changes one value and does not offer
    the cost comparison step 2's cards make (rendering.ProfileOfferView).
    """

    key: str
    label: str


def profile_options() -> list[ProfileOption]:
    return [ProfileOption(key=key, label=profile_display_name(key)) for key in PROFILE_KEYS]
