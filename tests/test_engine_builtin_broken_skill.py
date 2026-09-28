"""A broken skill file must never stop the product from starting.

Reproduces the failure found in review: a malformed skills/summarize.yaml
used to raise at import of engine.builtin, so every entrypoint, even
`voxtrama doctor`, whose only job is to diagnose a bad configuration,
refused to start. engine.skill_catalog's tolerant loading
(load_generative_skills, generative_registry) is what these tests protect.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import voxtrama.engine.builtin as builtin_module
import voxtrama.engine.skill_catalog as skill_catalog_module
from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.engine.skill_catalog import generative_registry, load_generative_skills
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill_file import SkillFileError


@pytest.fixture
def broken_summarize() -> Iterator[Path]:
    """A malformed user override of summarize.yaml, undone once the test is done.

    BUILTIN_STEPS/BUILTIN_SKILLS are module-level constants, built once at
    import. Reloading the module is the only way to re-run that
    construction against a different filesystem, and removing the file
    before the final reload keeps this test from leaking a broken
    registry into whatever test runs after it.
    """
    skills_dir = get_settings().data_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / "summarize.yaml"
    path.write_text("prompt: [this is not valid yaml\n")
    importlib.reload(builtin_module)
    yield path
    path.unlink()
    importlib.reload(builtin_module)


def _workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="Names the skill a broken user override shadows.",
        steps=[Step(id="summarize", skill="summarize", skill_version="1.0.0")],
    )


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def test_a_broken_user_override_never_stops_the_module_from_importing(
    broken_summarize: Path,
) -> None:
    assert "transcribe" in builtin_module.BUILTIN_STEPS
    assert "diarize" in builtin_module.BUILTIN_SKILLS
    # summarize still gets a step, so a run that names it fails saying why,
    # but never a Skill declaration nothing here could invent.
    assert "summarize" in builtin_module.BUILTIN_STEPS
    assert "summarize" not in builtin_module.BUILTIN_SKILLS


def test_a_run_naming_the_broken_skill_fails_with_the_file_and_the_parse_error(
    broken_summarize: Path, db_session: Session
) -> None:
    run = create_run(db_session, "test-workflow", "unpinned")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())
    context.transcript = _transcript()

    with pytest.raises(SkillFileError) as excinfo:
        execute_step(
            context,
            _workflow().steps[0],
            rows[0],
            builtin_module.BUILTIN_STEPS,
            builtin_module.BUILTIN_SKILLS,
        )
    assert str(broken_summarize) in str(excinfo.value)


def test_a_valid_skill_next_to_a_broken_one_loads_and_runs_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.yaml").write_text(
        "skill:\n"
        "  name: ok\n"
        "  version: 1.0.0\n"
        "  input_schema: {type: object}\n"
        "  output_schema: {type: object}\n"
        "  model_class: generative\n"
        "  minimum_model_profile: low\n"
        "  evidence_required: false\n"
        "  minimum_confidence: 0.0\n"
        "  review_required: false\n"
        "  retention_policy: follows_recording\n"
        "  privacy: any\n"
        "prompt: Hello, {language}.\n"
    )
    (tmp_path / "broken.yaml").write_text("prompt: [this is not valid yaml\n")
    monkeypatch.setattr(
        skill_catalog_module, "find_skill_file", lambda name: tmp_path / f"{name}.yaml"
    )

    steps, skills = generative_registry(load_generative_skills(["ok", "broken"]))

    assert "ok" in skills
    assert "broken" not in skills
    with pytest.raises(SkillFileError):
        steps["broken"](None)
