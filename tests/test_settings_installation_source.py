"""Tests for config.installation_source: Settings reading voxtrama.toml,
the guided setup's own output file. Split from test_settings.py to
stay under the project's 150-line file cap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.config.paths import installation_config_path
from voxtrama.config.settings import Settings, SettingsError, get_settings


def _write_installation_toml(data_dir: Path, body: str) -> None:
    installation_config_path(data_dir).write_text(body)


def test_the_installation_file_fills_settings_when_the_environment_is_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guided setup's own output must reach Settings on its own, with
    nobody having exported an environment variable for it.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VOXTRAMA_HARDWARE_PROFILE", raising=False)
    monkeypatch.delenv("VOXTRAMA_OLLAMA_MODEL", raising=False)
    _write_installation_toml(tmp_path, 'hardware_profile = "high"\nollama_model = "qwen3:4b"\n')
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.hardware_profile == "high"
    assert settings.ollama_model == "qwen3:4b"


def test_the_environment_wins_over_the_installation_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precedence, strongest first: init > env > dotenv > this file > default."""
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VOXTRAMA_HARDWARE_PROFILE", "low")
    _write_installation_toml(tmp_path, 'hardware_profile = "high"\n')
    get_settings.cache_clear()

    assert get_settings().hardware_profile == "low"


def test_the_installation_file_wins_over_the_fields_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VOXTRAMA_HARDWARE_PROFILE", raising=False)
    _write_installation_toml(tmp_path, 'hardware_profile = "high"\n')
    get_settings.cache_clear()

    assert get_settings().hardware_profile == "high"


def test_installation_file_keys_that_are_not_settings_fields_do_not_break_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Settings.model_config` has `extra="forbid"`: `InstallationConfig`'s
    own fields that `Settings` does not have yet (instance_token,
    cores_per_chunk, parallel_chunks, model_context_limits) must be
    filtered out rather than rejected wholesale.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    _write_installation_toml(
        tmp_path,
        'hardware_profile = "high"\n'
        'ollama_model = "qwen3:4b"\n'
        "cores_per_chunk = 4\n"
        "parallel_chunks = 2\n"
        'instance_token = "a-token"\n'
        "\n"
        "[model_context_limits]\n"
        '"qwen3:4b" = 8192\n',
    )
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.hardware_profile == "high"
    assert settings.ollama_model == "qwen3:4b"


def test_malformed_toml_falls_back_to_the_fields_default_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VOXTRAMA_HARDWARE_PROFILE", raising=False)
    _write_installation_toml(tmp_path, "not = [valid toml")
    get_settings.cache_clear()

    assert get_settings().hardware_profile == "base"


def test_a_value_the_schema_rejects_fails_startup_naming_the_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberately different from read_installation_config, which treats a
    broken file as absent: a Settings that silently ignored half its own
    file would be worse than one that refuses to start.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VOXTRAMA_HARDWARE_PROFILE", raising=False)
    _write_installation_toml(tmp_path, 'hardware_profile = "ultra"\n')
    get_settings.cache_clear()

    with pytest.raises(SettingsError) as excinfo:
        get_settings()

    assert "hardware_profile" in str(excinfo.value)


def test_a_hand_written_file_with_only_ollama_model_still_feeds_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`InstallationConfig` requires cores_per_chunk/parallel_chunks, so a
    file missing them is not valid for it. This test defends the
    choice of reading the TOML directly rather than through
    read_installation_config, which would discard this file whole and
    lose the one field it carries.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    _write_installation_toml(tmp_path, 'ollama_model = "qwen3:4b"\n')
    get_settings.cache_clear()

    assert get_settings().ollama_model == "qwen3:4b"


def test_data_dir_from_init_locates_the_installation_file(tmp_path: Path) -> None:
    """`data_dir` passed to the constructor, not the environment, still
    determines where the installation file is read from.
    """
    _write_installation_toml(tmp_path, 'ollama_model = "qwen3:4b"\n')

    settings = Settings(data_dir=tmp_path)

    assert settings.ollama_model == "qwen3:4b"
