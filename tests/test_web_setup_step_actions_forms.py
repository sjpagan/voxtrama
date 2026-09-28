"""The two forms .vx-step-actions now sits inside, split from
test_web_setup_step_actions.py to stay under the project's 150-line cap.

"Finish setup" moved one level deeper (inside .vx-step-actions, itself
inside <form>) and step 3's own "Continue" is a GET <form>. Both are
submitted here reading the rendered page's own fields, not a hand-typed
dict, the way a browser would.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.ollama_provider import fake_ollama_provider, reachable_probe, stub_model_facts
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.setup.generative_step as generative_step
from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.setup.installation import read_installation_config

_HIDDEN_INPUT = re.compile(r'<input type="hidden" name="([^"]+)" value="([^"]*)"')


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _hidden_fields(body: str) -> dict[str, str]:
    """Every `<input type="hidden">` on the page, theme_control.html's own
    "origin" field included: harmless noise a real re-POST/re-GET carries
    along too, the same as test_web_setup_flow.py's own helper.
    """
    return dict(_HIDDEN_INPUT.findall(body))


def test_finish_setup_still_submits_the_rendered_forms_own_hidden_fields(
    client: TestClient, tmp_path: Path
) -> None:
    """The regression to guard against: a button no longer part
    of its own form. Posting exactly what the rendered page carries is
    what would catch it.
    """
    body = client.get("/setup/private-storage").text

    posted = client.post(
        "/setup/private-storage", data=_hidden_fields(body), follow_redirects=False
    )

    assert posted.status_code == 303
    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.hardware_profile == "high"


def test_model_ready_continue_carries_ollama_model_and_context_limit_forward(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3's own "Continue" is a GET <form> (a fresh /api/show read
    needs a request), submitted here the way a browser would,
    every named field the rendered form itself carries, hidden or not.
    """
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"model-a": ModelFacts(context_length=4096, licence_text="MIT License")},
    )

    step3 = client.get("/setup/model-ready").text
    fields = _hidden_fields(step3)
    fields["context_limit"] = "4096"

    step4 = client.get("/setup/private-storage", params=fields).text

    assert 'name="ollama_model" value="model-a"' in step4
    assert 'name="context_limit" value="4096"' in step4
