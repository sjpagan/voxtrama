"""Tests for calibration.py: no synthesis, no ElevenLabs call, just the yaml.

Kept small: adding a language should cost copying a file and writing text,
not satisfying a battery of structural checks. See calibration/README.md.
"""

from __future__ import annotations

import generate
import pytest

import calibration

LANGUAGES = calibration.available_languages()


@pytest.mark.parametrize("language", LANGUAGES)
def test_language_matches_filename(language: str) -> None:
    script = calibration.load_script(language)
    assert script.language == language


@pytest.mark.parametrize("language", LANGUAGES)
def test_passages_are_non_empty_with_unique_ids(language: str) -> None:
    script = calibration.load_script(language)
    ids = [passage.id for passage in script.passages]
    assert len(ids) == len(set(ids))
    for passage in script.passages:
        assert passage.text.strip()


@pytest.mark.parametrize("language", LANGUAGES)
def test_scripted_duration_is_plausible(language: str) -> None:
    script = calibration.load_script(language)
    scripted = next(p for p in script.passages if p.id == "scripted")
    lines = [line for line in scripted.text.splitlines() if line.strip()]
    duration = sum(generate.estimate_duration(line) for line in lines)
    assert 15.0 <= duration <= 90.0
