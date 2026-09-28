"""Each profile card's own library commands: a licence link, and
"Download" / "Remove" wired to that card's own key, independent of
which profile the radio above has picked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.api.routes.setup_processing as setup_processing_route
from voxtrama.transcription.asr import weights_for


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_every_card_names_its_own_licence_with_a_link_to_its_page(client: TestClient) -> None:
    """The licence is a fact about the model, not a string typed
    into the template: "MIT" for whisper, linked to its Hugging Face page.
    """
    body = client.get("/setup/local-processing").text

    assert "MIT" in body
    assert 'class="vx-profile-card__licence"' in body
    assert "huggingface.co" in body


def test_a_cached_profile_shows_remove_and_the_others_show_download(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Downloading and removing a model are commands on the library,
    independent of which card the radio has picked. The hidden
    hardware_profile of *each* card's own form is that card's own key,
    never chosen_profile. This is the test that fails if a card's form
    gets rewired to the selection instead.
    """
    base_repo = weights_for("base").repo_id
    monkeypatch.setattr(
        setup_processing_route,
        "is_cached",
        lambda weights, _models_dir: weights.repo_id == base_repo,
    )

    body = client.get(
        "/setup/local-processing?hardware_profile=low&cores_per_chunk=4&parallel_chunks=2"
    ).text

    assert 'name="hardware_profile" value="low"' in body
    assert 'name="hardware_profile" value="base"' in body
    assert 'name="hardware_profile" value="high"' in body
    # "base" is cached (its form posts to remove-model, danger styled);
    # "low" and "high" are not (their form posts to origin, plain styled).
    assert "vx-button--danger vx-button--small" in body
    assert body.count("vx-button--small") == 3


def test_a_cached_profile_shows_installed_and_on_disk_not_download_size(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The "Download size" number means something else once the
    model is already on disk. The card must say so where the model's
    name is read, not only through the Remove button at the bottom.
    """
    base_repo = weights_for("base").repo_id
    monkeypatch.setattr(
        setup_processing_route,
        "is_cached",
        lambda weights, _models_dir: weights.repo_id == base_repo,
    )

    body = client.get(
        "/setup/local-processing?hardware_profile=low&cores_per_chunk=4&parallel_chunks=2"
    ).text

    # "base" is the only cached profile: one "Installed" badge, one "On
    # disk" caption, and the other two profiles keep "Download size".
    assert "Installed" in body
    assert "On disk" in body
    assert "Download size" in body


def test_an_uncached_profile_shows_download_size_not_installed(client: TestClient) -> None:
    """The other direction: without a cached model, nothing on the
    card claims it is installed. A badge that never turns off would
    still pass the test above.
    """
    body = client.get("/setup/local-processing").text

    assert "Download size" in body
    assert "On disk" not in body
    assert "Installed" not in body
