"""THIRD_PARTY_LICENSES.md matches requirements.lock.

The file is generated, never hand-edited: a dependency added or bumped with
`make lock` shows up here, or this test fails until
scripts/generate_third_party_licenses.py is run again.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_third_party_licenses.py"

spec = importlib.util.spec_from_file_location("generate_third_party_licenses", SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

# Licences that would stop Voxtrama from shipping under Apache-2.0 if one of
# its libraries carried them. A match is a decision for a person, not a bump.
_BLOCKING = ("GPL", "AGPL", "SSPL", "Commons Clause", "BUSL")


def test_the_committed_file_matches_the_lock() -> None:
    assert generator.OUTPUT.read_text(encoding="utf-8") == generator.render(), (
        "THIRD_PARTY_LICENSES.md is stale: run scripts/generate_third_party_licenses.py"
    )


def test_no_python_library_carries_a_copyleft_or_source_available_licence() -> None:
    blocked = [
        (name, licence)
        for name, _ in generator.pinned()
        if any(word in (licence := generator.licence_of(name)) for word in _BLOCKING)
        and "LGPL" not in licence
    ]
    assert not blocked, blocked
