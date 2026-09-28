"""GET and POST /setup: the writable overview of the installation's
own configuration: reading what the file holds, changing one value
without the four-step wizard, and declaring when the environment is why a
value shown is not the one in force (the environment takes precedence).
Each form's own scoped context_limit is
tests/test_web_setup_settings_context_limits.py, split out to stay under
the project's 150-line file cap.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.setup.installation import (
    InstallationConfig,
    read_installation_config,
    write_installation_config,
)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _write_config(tmp_path: Path, **overrides: object) -> InstallationConfig:
    fields: dict[str, object] = {
        "hardware_profile": "high",
        "cores_per_chunk": 4,
        "parallel_chunks": 2,
        "instance_token": "a-token",
        **overrides,
    }
    config = InstallationConfig(**fields)
    write_installation_config(tmp_path, config)
    return config


def test_a_first_run_with_no_installation_config_says_so_and_points_to_setup(
    client: TestClient,
) -> None:
    response = client.get("/setup")

    assert response.status_code == 200
    assert "has not been set up yet" in response.text
    assert "/setup/local-processing" in response.text


def test_the_page_shows_the_values_the_file_holds(client: TestClient, tmp_path: Path) -> None:
    _write_config(tmp_path, cores_per_chunk=6, parallel_chunks=3)

    body = client.get("/setup").text

    assert "Maximum accuracy" in body
    assert "3 chunks × 6 cores" in body
    # The "Change profile" form must not silently move the parallelism it
    # is not editing: it carries the file's own values forward as hidden
    # fields, not a fresh machine-based proposal (api.routes.setup_settings's
    # own docstring on why the two must never be confused).
    assert '<input type="hidden" name="cores_per_chunk" value="6" />' in body
    assert '<input type="hidden" name="parallel_chunks" value="3" />' in body


def test_saving_one_value_writes_it_and_it_reads_back_with_no_restart(
    client: TestClient, tmp_path: Path
) -> None:
    _write_config(tmp_path)

    response = client.post(
        "/setup",
        data={"hardware_profile": "low", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/setup"
    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.hardware_profile == "low"
    # No process restart happens between the write and this GET: the
    # same running app, the same cached Settings (write_installation_config
    # clears it), and the change is already visible.
    assert "Efficient" in client.get("/setup").text


def test_changing_the_profile_does_not_move_the_parallelism_it_did_not_touch(
    client: TestClient, tmp_path: Path
) -> None:
    _write_config(tmp_path, cores_per_chunk=6, parallel_chunks=3)

    client.post(
        "/setup", data={"hardware_profile": "low", "cores_per_chunk": 6, "parallel_chunks": 3}
    )

    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.cores_per_chunk == 6
    assert config.parallel_chunks == 3


def test_the_instance_token_survives_a_save(client: TestClient, tmp_path: Path) -> None:
    original = _write_config(tmp_path)

    client.post(
        "/setup", data={"hardware_profile": "base", "cores_per_chunk": 4, "parallel_chunks": 2}
    )

    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.instance_token == original.instance_token


def test_a_value_overridden_by_the_environment_is_declared_as_such(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file says "high"; VOXTRAMA_HARDWARE_PROFILE says "low" and, since
    the environment takes precedence, wins. The page must show the file's own value
    marked as overridden, not pretend the file is what runs.
    """
    _write_config(tmp_path)
    monkeypatch.setenv("VOXTRAMA_HARDWARE_PROFILE", "low")

    body = client.get("/setup").text

    assert "Maximum accuracy" in body
    assert "from environment" in body


def test_nothing_is_marked_overridden_when_the_environment_is_silent(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VOXTRAMA_HARDWARE_PROFILE", raising=False)
    _write_config(tmp_path)

    body = client.get("/setup").text

    assert "from environment" not in body
