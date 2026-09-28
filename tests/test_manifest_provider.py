"""The manifest says where a run's generative steps ran, never the host."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient

from voxtrama.config.paths import get_paths
from voxtrama.config.providers import ProviderConfig
from voxtrama.config.settings import Settings
from voxtrama.manifest.environment import provider_info

REMOTE = {"cloud": ProviderConfig(url="https://llm.example.com")}


def test_a_run_that_called_a_provider_records_its_name_and_locality(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, providers=REMOTE)

    info = provider_info(settings, "cloud", True)

    assert info.model_dump() == {"name": "cloud", "locality": "remote"}
    assert "example.com" not in json.dumps(info.model_dump())


def test_a_run_no_generative_step_ran_for_names_no_provider(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, providers=REMOTE)

    assert provider_info(settings, None, False) is None


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app)


def test_the_shared_manifest_takes_the_steps_hosts_out(client, tmp_path) -> None:
    path = get_paths(tmp_path).runs_dir / "job-1" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["steps"][0]["host"] = "llm.internal.example"
    path.write_text(json.dumps(manifest))

    shared = client.get("/runs/job-1/manifest.json").text

    assert "llm.internal.example" not in shared
