"""Puts fakes.reuse_steps' three-step workflow behind a real catalogue file.

test_engine_superseded_run_copy.py and test_engine_reconcile_workflow_copy.py both need a
run that resolved its workflow through engine.catalog.load_named_workflow for real. Every
other reuse test injects a Workflow object straight through execute_run's own `workflow=`
parameter, bypassing the catalogue entirely, and that is the path both copy-reading callers
must NOT take once a run has finished. fakes.reuse_steps.install patches
engine.run.BUILTIN_SKILLS for execution. load_named_workflow reads a second, separate
reference (engine.catalog's own), so this patches that one too.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fakes.reuse_steps import install
from fakes.workflow import fake_skill
from voxtrama.config.settings import get_settings
from voxtrama.engine import catalog as engine_catalog
from voxtrama.workflow.definition import Workflow

_FAKE_SKILL_NAMES = ("t", "t2", "d", "s1", "s2")


def install_catalog_workflow(monkeypatch: pytest.MonkeyPatch, calls: dict[str, int]) -> None:
    """fakes.reuse_steps.install, plus the catalogue's own copy of the fake registry."""
    install(monkeypatch, calls)
    monkeypatch.setattr(
        engine_catalog,
        "BUILTIN_SKILLS",
        {name: {"1.0.0": fake_skill(name)} for name in _FAKE_SKILL_NAMES},
    )


def write_catalog_workflow(workflow: Workflow) -> Path:
    """Write `workflow` as the user's own catalogue file for its own name.

    The user root, not the package's: writing here needs no fixture of our
    own, since every test already gets an isolated data_dir (conftest's
    `_queue_url_env`), and the user root is the one load_named_workflow
    prefers when both exist.
    """
    path = get_settings().data_dir / "workflows" / f"{workflow.name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(workflow.model_dump(mode="json")))
    return path
