"""The workflows we ship must load, validate and resolve, checked without models.

This is what stands between a typo in a shipped workflow file and a run that
fails inside a worker: it needs no audio and no weights, so it runs in CI
alongside everything else.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from voxtrama.config.settings import get_settings
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.catalog import (
    WorkflowNotFoundError,
    find_workflow_file,
    load_named_workflow,
)
from voxtrama.engine.steps import resolve_order

SHIPPED = sorted(p.stem for p in (Path(__file__).parents[1] / "workflows").glob("*.yaml"))


def test_the_repository_ships_at_least_the_minimal_workflow() -> None:
    assert "transcribe-only" in SHIPPED


def test_the_minimal_workflow_loads_and_resolves() -> None:
    workflow = load_named_workflow("transcribe-only")
    order = [step.id for step in resolve_order(workflow)]
    assert order == ["transcribe", "diarize"]


def test_every_step_of_the_minimal_workflow_has_an_implementation() -> None:
    """A workflow we ship may not name a skill the engine cannot run."""
    workflow = load_named_workflow("transcribe-only")
    missing = [step.skill for step in workflow.steps if step.skill not in BUILTIN_STEPS]
    assert missing == []


def test_every_built_in_step_is_also_a_declared_skill() -> None:
    """The loader validates against the registry: an implementation the
    registry does not declare could never be named by a workflow."""
    assert sorted(BUILTIN_STEPS) == sorted(BUILTIN_SKILLS)


@pytest.mark.parametrize("name", ["meeting-decisions", "lesson-companion", "research-interview"])
def test_each_par_7_example_workflow_loads_and_every_step_is_implemented(name: str) -> None:
    """The fix for SkillNotFoundError on all three, with no invented skill."""
    workflow = load_named_workflow(name)
    missing = [step.skill for step in workflow.steps if step.skill not in BUILTIN_STEPS]
    assert missing == []


@pytest.mark.parametrize("name", SHIPPED)
def test_every_shipped_workflow_declares_a_readable_title(name: str) -> None:
    """`title` is optional at the schema's own level (workflow.definition.
    Workflow's own docstring on why), but every workflow the package
    ships is not a throwaway test fixture. This is the one place that
    distinction is enforced."""
    workflow = load_named_workflow(name)
    assert workflow.title


def test_an_unknown_workflow_names_where_it_looked() -> None:
    with pytest.raises(WorkflowNotFoundError) as excinfo:
        find_workflow_file("no-such-workflow")
    assert "no-such-workflow" in str(excinfo.value)
    assert "workflows" in str(excinfo.value)


def test_a_users_workflow_file_wins_over_the_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """data_dir/workflows is the first root: a user's copy shadows ours, never the reverse."""
    package_root = tmp_path / "package"
    (package_root / "workflows").mkdir(parents=True)
    (package_root / "workflows" / "collide.yaml").write_text(yaml.safe_dump("package"))
    monkeypatch.chdir(package_root)

    data_dir = get_settings().data_dir
    (data_dir / "workflows").mkdir(parents=True)
    (data_dir / "workflows" / "collide.yaml").write_text(yaml.safe_dump("user"))

    found = find_workflow_file("collide")

    assert found == data_dir / "workflows" / "collide.yaml"


def test_a_root_that_cannot_be_read_does_not_block_the_next_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable data_dir/workflows is a root without the workflow, not a failure."""
    data_dir = get_settings().data_dir
    unreadable = data_dir / "workflows"
    unreadable.mkdir()
    unreadable.chmod(0o000)

    package_root = tmp_path / "package"
    (package_root / "workflows").mkdir(parents=True)
    (package_root / "workflows" / "findable.yaml").write_text(yaml.safe_dump("findable"))
    monkeypatch.chdir(package_root)

    try:
        found = find_workflow_file("findable")
    finally:
        unreadable.chmod(0o755)

    assert found == package_root / "workflows" / "findable.yaml"
