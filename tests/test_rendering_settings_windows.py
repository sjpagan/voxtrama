"""The settings line says when the transcript was read in windows."""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.schema import Manifest
from voxtrama.rendering.job_settings_line import settings_line


def _manifest(windows: int | None) -> Manifest:
    data = manifest_dict()
    for step in data["steps"]:
        step["transcript_windows"] = windows
    return Manifest.model_validate(data)


def test_a_split_transcript_shows_how_many_windows() -> None:
    assert settings_line(_manifest(5), "Meeting decisions", 3).windows == 5


def test_a_transcript_read_whole_shows_nothing() -> None:
    assert settings_line(_manifest(1), "Meeting decisions", 3).windows is None
    assert settings_line(_manifest(None), "Meeting decisions", 3).windows is None


def test_a_deduced_context_is_shown_as_deduced() -> None:
    data = manifest_dict()
    data["choices"]["context_deduced"] = "Topic: roadmap"

    line = settings_line(Manifest.model_validate(data), "Meeting decisions", 3)

    assert line.deduced_context == "Topic: roadmap" and not line.has_context
