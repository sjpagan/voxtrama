"""The row that closes a step (.vx-step-actions) always puts its
primary action last, not wherever the .vx-cluster it replaced happened to
render it. The two forms it now sits inside still submit for real (split
into tests/test_web_setup_step_actions_forms.py to stay under the
project's 150-line cap).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.ollama_provider import fake_ollama_provider, reachable_probe, stub_model_facts
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.setup.generative_step as generative_step
from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.providers.probe import ProviderProbe


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _primary_is_last(body: str, primary_text: str, start_text: str | None = None) -> None:
    """.vx-step-actions always renders its left slot before its right one
    (components/step_actions.html emits both, one never dropped even when
    empty). This checks `primary_text` sits in the second slot,
    after whatever the first one holds.
    """
    idx = body.index('class="vx-step-actions"')
    tail = body[idx:]
    start_idx = tail.index("vx-step-actions__start")
    primary_idx = tail.index("vx-step-actions__primary")
    assert start_idx < primary_idx
    assert primary_text in tail[primary_idx:]
    if start_text:
        assert start_text in tail[start_idx:primary_idx]


def test_an_old_personal_settings_link_opens_the_first_step_now(client: TestClient) -> None:
    """The name left the guided setup. An old link lands on its first step."""
    response = client.get("/profile", params={"setup": "true"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/setup/local-processing"


def test_local_processing_step_puts_download_last_with_nothing_before_it(
    client: TestClient,
) -> None:
    body = client.get(
        "/setup/local-processing",
        params={"hardware_profile": "low", "cores_per_chunk": 4, "parallel_chunks": 2},
    ).text
    _primary_is_last(body, "Download selected model")


def test_model_ready_step_puts_skip_last_when_nothing_else_is_offered(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unreachable = ProviderProbe(
        reachable=False, latency_seconds=None, version=None, models=(), error="refused"
    )
    monkeypatch.setattr(generative_step, "OllamaProvider", fake_ollama_provider(unreachable))

    body = client.get("/setup/model-ready").text

    _primary_is_last(body, "Skip (no generative model)")


def test_model_ready_step_puts_continue_after_skip_when_a_model_is_selected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"model-a": ModelFacts(context_length=4096, licence_text="MIT License")},
    )

    body = client.get("/setup/model-ready").text

    _primary_is_last(body, "Continue", start_text="Skip (no generative model)")


def test_private_storage_step_puts_finish_setup_last_with_nothing_before_it(
    client: TestClient,
) -> None:
    """The left slot has been empty since «Try the demo» was removed: it was
    a link to the home page, where the button of the same name did nothing.
    The rule this file checks does not change (the primary action sits in
    the second slot) and still holds with the first slot empty.
    """
    body = client.get("/setup/private-storage").text
    _primary_is_last(body, "Finish setup")
    assert "Try the demo" not in body
