"""GET /runs/{id}/manifest.json: shared without the context's text."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient

from voxtrama.config.paths import get_paths

CONTEXT = "Participants: Giulia Rossi, Marco Bianchi. Product: Voxtrama."


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    path = get_paths(tmp_path).runs_dir / "job-1" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["choices"]["context"] = CONTEXT
    manifest["choices"]["context_cut_for_transcription"] = False
    path.write_text(json.dumps(manifest))
    return TestClient(app)


def test_the_shared_manifest_says_a_context_was_given_not_what_it_said(client, tmp_path) -> None:
    response = client.get("/runs/job-1/manifest.json")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "Giulia" not in response.text and "Marco" not in response.text
    shared = response.json()
    assert shared["choices"]["context"] == "[removed]"
    assert shared["choices"]["context_cut_for_transcription"] is False


def test_the_manifest_on_disk_keeps_the_context(client, tmp_path) -> None:
    client.get("/runs/job-1/manifest.json")

    on_disk = get_paths(tmp_path).runs_dir / "job-1" / "manifest.json"
    assert json.loads(on_disk.read_text())["choices"]["context"] == CONTEXT


def test_the_export_menu_offers_the_manifest(client) -> None:
    assert 'href="/runs/job-1/manifest.json"' in client.get("/runs/job-1/view").text


def test_a_job_without_a_manifest_is_404(client) -> None:
    assert client.get("/runs/nobody/manifest.json").status_code == 404


def test_a_deduced_context_is_taken_out_too(client, tmp_path) -> None:
    path = get_paths(tmp_path).runs_dir / "job-1" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["choices"]["context"] = None
    manifest["choices"]["context_deduced"] = "People: Giulia Rossi"
    path.write_text(json.dumps(manifest))

    shared = client.get("/runs/job-1/manifest.json").json()

    assert shared["choices"]["context_deduced"] == "[removed]"


def test_the_model_server_is_named_nowhere_in_the_shared_copy(client, tmp_path) -> None:
    """An error names its host too, not only steps[].host."""
    path = get_paths(tmp_path).runs_dir / "job-1" / "manifest.json"
    manifest = json.loads(path.read_text())
    step = manifest["steps"][-1]
    step["host"] = "gpu.lan:11434"
    step["error"] = "http://gpu.lan:11434/api/generate is unreachable: refused"
    manifest["failure"] = {
        "code": "provider_credentials",
        "message": "gpu.lan:11434 requires credentials",
        "step": None,
    }
    path.write_text(json.dumps(manifest))

    body = client.get("/runs/job-1/manifest.json").text

    assert "gpu.lan" not in body
    assert "[removed] requires credentials" in body
