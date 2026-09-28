"""Loads calibration scripts from calibration/<language>.yaml.

A calibration script is what a person installing Voxtrama reads out loud, and
what the `calibration-*` cases in cases.yaml make a synthetic voice read
instead. Adding a language means adding a file under calibration/, not
touching this module: see calibration/README.md for the format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CALIBRATION_DIR = Path(__file__).resolve().parents[3] / "calibration"


class CalibrationError(Exception):
    """Raised when a calibration script cannot be found or parsed."""


@dataclass(frozen=True)
class Passage:
    """One reading passage of a calibration script (`scripted` or `unpredictable`)."""

    id: str
    kind: str
    text: str


@dataclass(frozen=True)
class CalibrationScript:
    language: str
    version: str
    passages: list[Passage]


def available_languages() -> list[str]:
    """Languages with a script under calibration/, derived from the files present."""
    return sorted(path.stem for path in CALIBRATION_DIR.glob("*.yaml"))


def load_script(language: str) -> CalibrationScript:
    """Load calibration/<language>.yaml, failing clearly if it does not exist."""
    path = CALIBRATION_DIR / f"{language}.yaml"
    if not path.is_file():
        available = ", ".join(available_languages()) or "none"
        raise CalibrationError(
            f"no calibration script for language '{language}'; available: {available}"
        )
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    passages = [Passage(id=p["id"], kind=p["kind"], text=p["text"]) for p in raw["passages"]]
    return CalibrationScript(
        language=raw["language"], version=str(raw["version"]), passages=passages
    )
