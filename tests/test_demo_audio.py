"""Finding the demo's audio, from a clone and from the image."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama import demo
from voxtrama.demo import DEMO_WORKFLOW, DemoAudioMissing, find_demo_audio

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_demo_audio_is_found_from_a_clone() -> None:
    """The fixture the tests use is the one the demo runs: one file, two uses."""
    found = find_demo_audio(start=REPO_ROOT)

    assert found.is_file()
    assert found.name == "public-fixture.wav"


def test_it_is_found_from_a_subdirectory_too(tmp_path: Path) -> None:
    """Someone running the demo from anywhere inside their clone still gets it."""
    found = find_demo_audio(start=REPO_ROOT / "src" / "voxtrama")

    assert found.is_file()


def test_the_workflow_the_demo_runs_is_one_we_ship() -> None:
    assert (REPO_ROOT / "workflows" / f"{DEMO_WORKFLOW}.yaml").is_file()


def test_not_finding_it_says_where_it_looked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that does not exist is a worse error than a sentence naming both.

    The image path is redirected because inside the container it really is
    there, and a test that passes only outside the container is the kind
    this project must stop shipping.
    """
    monkeypatch.setattr(demo, "IMAGE_DEMO_AUDIO", tmp_path / "absent" / "public-fixture.wav")
    with pytest.raises(DemoAudioMissing) as raised:
        find_demo_audio(start=tmp_path)

    message = str(raised.value)
    assert "public-fixture.wav" in message
    assert "tests/fixtures/public-fixture.wav" in message
