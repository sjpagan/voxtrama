"""A conditional-branch workflow run to completion, through the CLI rather than the engine.

test_engine_conditional.py covers a branch via execute_run directly. This
proves `voxtrama run` itself drives it to `succeeded`, CLI -> queue -> engine.
No model is downloaded, no audio transcribed: the built-ins are replaced with
fakes registered in the registries the real ones live in.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.workflow import (
    SynchronousQueue,
    fake_flag,
    fake_import_local_file,
    fake_noop,
    fake_skill,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

import voxtrama.cli.commands.run as run_command
import voxtrama.engine.catalog as engine_catalog
import voxtrama.engine.run as engine_run
from voxtrama.cli.main import app
from voxtrama.config.settings import get_settings
from voxtrama.db.models import Base, RunStep, StepState

runner = CliRunner()

_WORKFLOW_NAME = "cli-branch-workflow"

# transcribe -> summarize in sequence, plus "flag": a branch whose condition
# is always false for this test's recording, so it is the step never taken.
_WORKFLOW_YAML = """\
name: cli-branch-workflow
version: 1.0.0
schema_version: v1
description: Test-only workflow for `voxtrama run`, end to end.
steps:
  - id: transcribe
    skill: transcribe
    skill_version: 1.0.0
  - id: summarize
    skill: summarize
    skill_version: 1.0.0
    depends_on: [transcribe]
  - id: flag
    skill: flag
    skill_version: 1.0.0
    depends_on: [transcribe]
    condition: "recording.duration_seconds < 10"
"""


def test_run_command_drives_a_branching_workflow_to_succeeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake audio")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(run_command, "build_session_factory", lambda: session_factory)
    monkeypatch.setattr(run_command, "import_local_file", fake_import_local_file)
    # Patched in both places: the catalogue validates against engine.catalog's
    # BUILTIN_SKILLS, the engine looks up implementations against its own.
    fake_skills = {
        name: {"1.0.0": fake_skill(name)} for name in ("transcribe", "summarize", "flag")
    }
    fake_steps = {"transcribe": fake_noop, "summarize": fake_noop, "flag": fake_flag}
    monkeypatch.setattr(engine_catalog, "BUILTIN_SKILLS", fake_skills)
    monkeypatch.setattr(engine_run, "BUILTIN_SKILLS", fake_skills)
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", fake_steps)

    workflows_dir = get_settings().data_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{_WORKFLOW_NAME}.yaml").write_text(_WORKFLOW_YAML)

    fake_queue = SynchronousQueue(session_factory)
    monkeypatch.setattr(run_command, "_build_queue", lambda: fake_queue)

    result = runner.invoke(app, ["run", _WORKFLOW_NAME, str(audio)])

    assert result.exit_code == 0
    run_id = fake_queue.submitted_run_ids[0]

    with session_factory() as session:
        rows = {
            row.step_id: row.state
            for row in session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
        }
    assert rows["transcribe"] == StepState.SUCCEEDED
    assert rows["summarize"] == StepState.SUCCEEDED
    assert rows["flag"] == StepState.SKIPPED
