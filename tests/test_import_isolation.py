"""Every entrypoint and package must import in a clean interpreter.

The suite itself can never catch a circular import: by the time any test
runs, pytest has already imported half the tree in an order that happens
to work. A cycle only shows up when a module is the *first* thing an
interpreter loads, which is what `python -m voxtrama.worker.main`
does in the container, and what `voxtrama doctor` does on a laptop.

Such a cycle once shipped: `transcription.resources` imported
`diagnostics.machine`, `tuning.selector` and `setup.core_budget` at module
level, each of which reaches back to `voxtrama.transcription` before it has
finished initialising. The whole suite stayed green while the worker
crash-looped on startup and the CLI would not run at all.

One subprocess per module, so each gets a genuinely fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# The three ways this package is started.
ENTRYPOINTS = ["voxtrama.api.app", "voxtrama.worker.main", "voxtrama.cli.main"]

# Packages that import cleanly on their own (measured). A new name belongs
# here as soon as it is clean.
PACKAGES = [
    "voxtrama.calibration",
    "voxtrama.config",
    "voxtrama.db",
    "voxtrama.diagnostics",
    "voxtrama.diarization",
    "voxtrama.engine",
    "voxtrama.i18n",
    "voxtrama.ingest",
    "voxtrama.logs",
    "voxtrama.manifest",
    "voxtrama.providers",
    "voxtrama.queue",
    "voxtrama.rendering",
    "voxtrama.setup",
    "voxtrama.transcription",
    "voxtrama.tuning",
    "voxtrama.weights",
    "voxtrama.workflow",
]


def _imports_alone(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("module", ENTRYPOINTS)
def test_every_entrypoint_imports_first_in_a_clean_interpreter(module: str) -> None:
    """`python -m voxtrama.worker.main` is not a hypothetical: it is the
    worker's own command line in compose.yaml.
    """
    result = _imports_alone(module)

    assert result.returncode == 0, f"{module} cannot be imported first:\n{result.stderr}"


@pytest.mark.parametrize("module", PACKAGES)
def test_every_package_imports_first_in_a_clean_interpreter(module: str) -> None:
    """A package that cannot be imported on its own is a cycle waiting for
    whichever entrypoint happens to reach it first.
    """
    result = _imports_alone(module)

    assert result.returncode == 0, f"{module} cannot be imported first:\n{result.stderr}"
