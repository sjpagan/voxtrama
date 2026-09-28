"""setup.installation: the TOML round trip and first-run detection."""

from __future__ import annotations

from pathlib import Path

from voxtrama.setup.installation import (
    InstallationConfig,
    installation_config_path,
    is_first_run,
    read_installation_config,
    write_installation_config,
)


def test_a_fresh_data_dir_is_a_first_run(tmp_path: Path) -> None:
    assert is_first_run(tmp_path) is True
    assert read_installation_config(tmp_path) is None


def test_writing_then_reading_back_gives_the_same_values(tmp_path: Path) -> None:
    config = InstallationConfig(
        hardware_profile="high",
        cores_per_chunk=8,
        parallel_chunks=2,
        model_context_limits={"qwen3:30b-a3b-instruct": 32768},
        ollama_model="qwen3:30b-a3b-instruct",
        instance_token="a-token",
    )

    write_installation_config(tmp_path, config)

    assert is_first_run(tmp_path) is False
    reread = read_installation_config(tmp_path)
    assert reread == config


def test_the_file_is_toml_readable_by_a_person(tmp_path: Path) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(hardware_profile="base", cores_per_chunk=4, parallel_chunks=2)
    )

    body = installation_config_path(tmp_path).read_text()

    assert 'hardware_profile = "base"' in body
    assert installation_config_path(tmp_path).name == "voxtrama.toml"


def test_a_malformed_file_reads_as_a_first_run_rather_than_raising(tmp_path: Path) -> None:
    installation_config_path(tmp_path).write_text("not = [valid toml")

    assert read_installation_config(tmp_path) is None


def test_a_model_context_limit_with_a_colon_in_its_name_round_trips(tmp_path: Path) -> None:
    """Ollama model names carry a colon (qwen3:30b-a3b-instruct); TOML bare
    keys cannot, so the writer must quote the key. This is the case that
    would silently corrupt the file if it did not.
    """
    config = InstallationConfig(
        hardware_profile="base",
        cores_per_chunk=1,
        parallel_chunks=1,
        model_context_limits={"qwen3:30b-a3b-instruct": 16384},
    )

    write_installation_config(tmp_path, config)

    assert read_installation_config(tmp_path).model_context_limits == {
        "qwen3:30b-a3b-instruct": 16384
    }
