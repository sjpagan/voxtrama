"""The custom-workflow limit is enforced where workflows are listed, looked
up and written: removing one check leaves the other two.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.config.settings import get_settings
from voxtrama.edition import EditionPolicy, PolicyLimitError
from voxtrama.engine import catalog
from voxtrama.workflow import custom_limit

_SHIPPED = "meeting-decisions"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    policy = EditionPolicy(custom_workflows=1, profile_fields=frozenset())
    monkeypatch.setattr(custom_limit, "current_policy", lambda: policy)
    yield tmp_path
    get_settings.cache_clear()


def _write(data_dir: Path, name: str) -> None:
    folder = data_dir / "workflows"
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.yaml").write_text("name: x\n", encoding="utf-8")


def test_a_copy_covering_a_shipped_workflow_is_not_custom(data_dir: Path) -> None:
    _write(data_dir, _SHIPPED)

    assert _SHIPPED not in custom_limit.custom_workflow_names()


def test_workflows_beyond_the_limit_are_not_listed_nor_found(data_dir: Path) -> None:
    _write(data_dir, "alpha-custom")
    _write(data_dir, "beta-custom")

    names = catalog.list_workflow_names()
    assert "alpha-custom" in names
    assert "beta-custom" not in names
    with pytest.raises(catalog.WorkflowNotFoundError):
        catalog.find_workflow_file("beta-custom")


def test_writing_a_second_custom_workflow_is_refused(data_dir: Path) -> None:
    _write(data_dir, "alpha-custom")

    custom_limit.ensure_room_for("alpha-custom")
    custom_limit.ensure_room_for(_SHIPPED)
    with pytest.raises(PolicyLimitError):
        custom_limit.ensure_room_for("beta-custom")
