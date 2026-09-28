"""Public surface of the configuration package."""

from voxtrama.config.paths import Paths, default_data_dir, get_paths
from voxtrama.config.settings import Settings, SettingsError, get_settings

__all__ = [
    "Settings",
    "SettingsError",
    "get_settings",
    "Paths",
    "get_paths",
    "default_data_dir",
]
