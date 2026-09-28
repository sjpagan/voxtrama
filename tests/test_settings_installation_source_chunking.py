"""cores_per_chunk/parallel_chunks reaching Settings from voxtrama.toml.

Split from test_settings_installation_source.py to stay under the
project's 150-line file cap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.config.paths import installation_config_path
from voxtrama.config.settings import get_settings


def _write_installation_toml(data_dir: Path, body: str) -> None:
    installation_config_path(data_dir).write_text(body)


def test_the_installation_file_fills_cores_per_chunk_and_parallel_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guided setup always writes both: once
    Settings has the fields, InstallationConfigSource lets them through
    with no change to that class (see its own docstring).
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VOXTRAMA_CORES_PER_CHUNK", raising=False)
    monkeypatch.delenv("VOXTRAMA_PARALLEL_CHUNKS", raising=False)
    _write_installation_toml(tmp_path, "cores_per_chunk = 4\nparallel_chunks = 2\n")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.cores_per_chunk == 4
    assert settings.parallel_chunks == 2


def test_the_environment_overrides_the_installation_file_for_cores_per_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VOXTRAMA_CORES_PER_CHUNK", "8")
    _write_installation_toml(tmp_path, "cores_per_chunk = 4\nparallel_chunks = 2\n")
    get_settings.cache_clear()

    assert get_settings().cores_per_chunk == 8
