"""rendering.setup_settings: telling a file's own value apart from one the
environment has overridden.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.config.settings import Settings
from voxtrama.rendering.setup_settings import profile_options, settings_overview_view
from voxtrama.setup.installation import InstallationConfig


def _config(**overrides: object) -> InstallationConfig:
    fields: dict[str, object] = {
        "hardware_profile": "high",
        "cores_per_chunk": 4,
        "parallel_chunks": 2,
        "ollama_model": "qwen3:4b",
        "ollama_url": "http://host.docker.internal:11434",
        **overrides,
    }
    return InstallationConfig(**fields)


def test_every_field_reads_from_the_file_when_settings_agrees_with_it(tmp_path: Path) -> None:
    config = _config()
    settings = Settings(
        data_dir=tmp_path,
        hardware_profile=config.hardware_profile,
        cores_per_chunk=config.cores_per_chunk,
        parallel_chunks=config.parallel_chunks,
        ollama_model=config.ollama_model,
        ollama_url=config.ollama_url,
    )

    overview = settings_overview_view(config, settings)

    assert overview.hardware_profile.from_environment is False
    assert overview.parallelism.from_environment is False
    assert overview.generative_model.from_environment is False
    assert overview.provider_address.from_environment is False
    assert overview.hardware_profile.value == "Maximum accuracy"
    assert overview.parallelism.value == "2 chunks × 4 cores"
    assert overview.generative_model.value == "qwen3:4b"


def test_a_field_settings_disagrees_with_is_flagged_from_the_environment(tmp_path: Path) -> None:
    config = _config(hardware_profile="high")
    settings = Settings(data_dir=tmp_path, hardware_profile="low")

    overview = settings_overview_view(config, settings)

    # The file's own value is still what is shown. Only the flag changes.
    assert overview.hardware_profile.value == "Maximum accuracy"
    assert overview.hardware_profile.from_environment is True


def test_parallelism_is_flagged_when_either_of_its_two_numbers_disagrees(tmp_path: Path) -> None:
    config = _config(cores_per_chunk=4, parallel_chunks=2)
    settings = Settings(data_dir=tmp_path, cores_per_chunk=8, parallel_chunks=2)

    overview = settings_overview_view(config, settings)

    assert overview.parallelism.from_environment is True


def test_a_generative_model_never_configured_shows_a_dash(tmp_path: Path) -> None:
    config = _config(ollama_model=None, ollama_url=None)
    settings = Settings(data_dir=tmp_path)

    overview = settings_overview_view(config, settings)

    assert overview.generative_model.value == "-"
    assert overview.generative_model.from_environment is False


def test_profile_options_cover_all_three_hardware_profiles() -> None:
    options = profile_options()

    assert [option.key for option in options] == ["low", "base", "high"]
    assert [option.label for option in options] == ["Efficient", "Balanced", "Maximum accuracy"]
