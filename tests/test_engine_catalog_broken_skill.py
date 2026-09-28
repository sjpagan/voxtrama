"""The message a person reads when their own skill file is broken.

Kept apart from test_engine_builtin_broken_skill.py, which protects the
registry: this protects the sentence. A skill whose file did not load is
absent from the registry, so the workflow validator can only call it
unknown: true of the registry, false of the world. Someone reading
"unknown skill 'summarize'" goes looking for a typo in the name instead of
a comma in their own YAML, which is the error that lies about its cause.
engine.catalog looks the real reason up and says it, once the workflow has
already been rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import voxtrama.engine.catalog as catalog_module
from voxtrama.engine.builtin import DIARIZE, TRANSCRIBE
from voxtrama.engine.skill_catalog import builtin_generative_registry
from voxtrama.workflow.loader import SkillNotFoundError

_WORKFLOW = """\
name: names-summarize
version: 1.0.0
schema_version: v1
description: A workflow naming the one generative skill.
steps:
  - id: s
    skill: summarize
    skill_version: 1.0.0
"""


@pytest.fixture
def user_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data directory holding both roots, so neither shipped file is touched."""
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "workflows" / "names-summarize.yaml").write_text(_WORKFLOW)
    yield tmp_path
    get_settings.cache_clear()


def _patch_builtin_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuild catalog.BUILTIN_SKILLS from whatever is on disk right now.

    Not importlib.reload, which this used to do: reload re-executes the
    module body, which builds a *new* WorkflowNotFoundError class object in
    place of the old one. Any module that had already imported the class by
    reference (engine.catalog's own callers, e.g. api/routes/run_create.py)
    keeps pointing at the old object, so its `except WorkflowNotFoundError`
    silently stops matching what this module raises from then on: whether
    that shows up depends on which test file pytest happens to run first,
    which is the bug review once caught. monkeypatch only swaps
    the dict, and undoes it itself at teardown. No class is ever rebuilt.
    """
    _, generative_skills = builtin_generative_registry()
    skills = {
        TRANSCRIBE.name: {TRANSCRIBE.version: TRANSCRIBE},
        DIARIZE.name: {DIARIZE.version: DIARIZE},
        **generative_skills,
    }
    monkeypatch.setattr(catalog_module, "BUILTIN_SKILLS", skills)


def test_a_broken_skill_file_is_named_instead_of_being_called_unknown(
    user_roots: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = user_roots / "skills" / "summarize.yaml"
    broken.write_text("prompt: [this is not a skill\n")
    _patch_builtin_skills(monkeypatch)

    with pytest.raises(SkillNotFoundError) as excinfo:
        catalog_module.load_named_workflow("names-summarize")

    message = str(excinfo.value)
    assert "summarize" in message
    # The file, so the reader knows where to look, and the parser's own
    # complaint, so they know what to look for.
    assert str(broken) in message
    assert "did not load" in message


def test_a_genuinely_unknown_skill_is_still_called_unknown(user_roots: Path) -> None:
    """The added sentence must not turn every unknown skill into a file problem."""
    (user_roots / "workflows" / "names-nothing.yaml").write_text(
        _WORKFLOW.replace("names-summarize", "names-nothing").replace("summarize", "no-such-skill")
    )

    with pytest.raises(SkillNotFoundError) as excinfo:
        catalog_module.load_named_workflow("names-nothing")

    assert "no-such-skill" in str(excinfo.value)
    assert "did not load" not in str(excinfo.value)
