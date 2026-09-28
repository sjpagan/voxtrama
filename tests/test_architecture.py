"""Executable check for the layer architecture: every module under src/voxtrama classified.

The layer data and its helpers live in _architecture.py, shared with
test_architecture_imports.py, which checks the import-direction rule
those layers exist for. test_architecture_boundaries.py holds the
queue/base.py and "no tracked media" boundaries. Three files for three
distinct rules, so none of them grows past the 150-line threshold they
all enforce on everyone else.
"""

from __future__ import annotations

from _architecture import classify, module_name, voxtrama_modules


def test_every_module_is_classified():
    unclassified = [
        m for path in voxtrama_modules() if (m := module_name(path)) and classify(m) is None
    ]
    assert not unclassified, f"unclassified modules (add them to a layer in LAYERS): {unclassified}"
