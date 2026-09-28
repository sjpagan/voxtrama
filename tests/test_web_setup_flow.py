"""The guided setup walked start to finish, using
only what each page's markup exposes, never a hardcoded next URL taken
from having read the route. Every page in isolation already passed;
this is the test that would have caught defect 1, where step 2's own
"Continue" existed in the HTML but only inside a closed `<details>`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.ollama_provider import fake_ollama_provider
from fakes.page_visibility import visible_text
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.api.routes.setup_processing as setup_processing_route
import voxtrama.setup.generative_step as generative_step
from voxtrama.providers.probe import ProviderProbe
from voxtrama.setup.installation import read_installation_config

_HIDDEN_INPUT = re.compile(r'<input type="hidden" name="([^"]+)" value="([^"]*)"')
_FORM = re.compile(r'<form method="post" action="([^"]+)".*?</form>', re.DOTALL)
# A link is found by the words a person reads, not by what sits between
# them and the tag: every sidebar anchor has an icon inside it, and a
# pattern that demanded the text touch the tag stopped matching a link
# that was still perfectly there. Anything may sit around the text.
_HREF_BY_TEXT = r'<a href="([^"]+)"[^>]*>(?:(?!</a>).)*?{}(?:(?!</a>).)*?</a>'


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _hidden_fields(body: str) -> dict[str, str]:
    """Every `<input type="hidden">` on the page: the values a real
    submission would carry along without a person ever seeing them.
    """
    return dict(_HIDDEN_INPUT.findall(body))


def _form_action(body: str, marker: str) -> str:
    """Where the one `<form method="post">` containing `marker` submits to.

    The header's own theme-switch form also posts on every page;
    scoping the search to a field or button unique to the step's own form
    is what keeps this from picking that one by accident.
    """
    for match in _FORM.finditer(body):
        if marker in match.group(0):
            return match.group(1)
    raise AssertionError(f"no POST form containing {marker!r} on this page")


def _href_of_or_none(body: str, text: str) -> str | None:
    """The href of the link a person would click on, or None if no link
    carries that text (markup between the tag and the words included).
    """
    match = re.search(_HREF_BY_TEXT.format(re.escape(text)), body, re.DOTALL)
    return match.group(1) if match else None


def _href_of(body: str, text: str) -> str:
    """The href of the one visible link whose own text is `text`.

    Reads `visible_text` first so a link that exists only inside a closed
    `<details>` (defect 1's own shape) fails this lookup instead of being
    followed as if it were reachable.
    """
    assert text in visible_text(body), f"{text!r} is not visible on this page"
    match = re.search(_HREF_BY_TEXT.format(re.escape(text)), body, re.DOTALL)
    assert match is not None, f"no link named {text!r} on this page"
    return match.group(1)


def _walk_to_processing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    """The name left the wizard, which opens on Local processing now.

    Steps 1-2 as they were, ending with the URL step 2's own visible "Continue" leads
    to. The queue and worker mechanics behind a real download have their
    own tests (test_web_setup_download.py); `is_cached` stands in for a
    download having already finished.

    Starts at the home page's own sidebar, not at a URL this test typed:
    the entry point is as much a part of the walk as the steps are. Taking
    it from the markup is what makes this test able to catch an entry that
    points at the wrong step, which is how it was found pointing at step
    2, leaving step 1 reachable by nobody. `Setup` opens the overview
    first, and its own "Go to setup" leads on from there.
    """
    overview_url = _href_of(client.get("/").text, "Settings")
    overview = client.get(overview_url).text
    step2_url = _href_of(overview, "Go to setup")
    assert "Personal settings" not in visible_text(client.get(step2_url).text)

    # Step 2, Local processing: the primary action is
    # visible before the model is cached, not only inside Fine-tune.
    step2 = client.get(step2_url).text
    assert "Download selected model" in visible_text(step2)

    monkeypatch.setattr(setup_processing_route, "is_cached", lambda *_a, **_kw: True)
    step2_ready = client.get(step2_url).text
    return _href_of(step2_ready, "Continue")


def test_the_whole_wizard_is_walkable_using_only_what_each_page_exposes(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert read_installation_config(tmp_path) is None
    step3_url = _walk_to_processing(client, monkeypatch)

    # Step 3, Model ready: nothing answers the standard address in this
    # test's own environment either, so the wizard proceeds via the
    # always-visible "Skip", pinned with a fake rather
    # than a real socket, the same as test_web_setup_processing.py.
    unreachable = ProviderProbe(
        reachable=False, latency_seconds=None, version=None, models=(), error="refused"
    )
    monkeypatch.setattr(generative_step, "OllamaProvider", fake_ollama_provider(unreachable))
    step3 = client.get(step3_url).text
    step4_url = _href_of(step3, "Skip (no generative model)")

    # Step 4, Private storage: the visible form's own hidden fields are
    # what gets submitted, not values this test invented.
    step4 = client.get(step4_url).text
    assert "Ready to start" in visible_text(step4)
    action = _form_action(step4, "hardware_profile")
    finished = client.post(action, data=_hidden_fields(step4), follow_redirects=False)

    assert finished.status_code == 303
    assert finished.headers["location"] == "/"
    assert read_installation_config(tmp_path) is not None
    assert (tmp_path / "voxtrama.toml").is_file()
    # `Setup` stays in the sidebar past the first run: rerunning auto-tune
    # or swapping the generative model are ordinary things to come back and
    # do, not a one-time wizard.
    assert _href_of_or_none(client.get("/").text, "Settings") is not None
