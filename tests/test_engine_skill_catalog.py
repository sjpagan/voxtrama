"""Find a generative skill's file by name, across the two places skill files live.

Mirrors tests/test_engine_catalog.py: no models, no audio, just the roots
and the precedence fixed for workflows, which this module repeats for
skills.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from voxtrama.config.settings import get_settings
from voxtrama.engine.skill_catalog import (
    SkillFileNotFoundError,
    find_skill_file,
    load_named_skill_file,
)

SHIPPED = sorted(p.stem for p in (Path(__file__).parents[1] / "skills").glob("*.yaml"))


def test_the_repository_ships_at_least_summarize() -> None:
    assert "summarize" in SHIPPED


def test_a_shipped_skill_loads_and_is_generative() -> None:
    skill_file = load_named_skill_file("summarize")

    assert skill_file.skill.name == "summarize"


@pytest.mark.parametrize("name", ["extract_decisions", "extract_concepts", "extract_themes"])
def test_each_extractor_skill_loads_and_is_generative(name: str) -> None:
    """The three skills the reduced workflows now name."""
    skill_file = load_named_skill_file(name)

    assert skill_file.skill.name == name
    assert skill_file.skill.model_class == "generative"


def test_an_unknown_skill_names_where_it_looked() -> None:
    with pytest.raises(SkillFileNotFoundError) as excinfo:
        find_skill_file("no-such-skill")
    assert "no-such-skill" in str(excinfo.value)
    assert "skills" in str(excinfo.value)


def test_a_users_skill_file_wins_over_the_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """data_dir/skills is the first root: a user's copy shadows ours, never the reverse."""
    package_root = tmp_path / "package"
    (package_root / "skills").mkdir(parents=True)
    (package_root / "skills" / "collide.yaml").write_text(yaml.safe_dump("package"))
    monkeypatch.chdir(package_root)

    data_dir = get_settings().data_dir
    (data_dir / "skills").mkdir(parents=True)
    (data_dir / "skills" / "collide.yaml").write_text(yaml.safe_dump("user"))

    found = find_skill_file("collide")

    assert found == data_dir / "skills" / "collide.yaml"
