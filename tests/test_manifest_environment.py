"""build_manifest's environment section: cpu_threads/num_workers.

Split from test_manifest_sections.py, which covers the rest of environment
and the other run-level sections. Same split as sections.py/
environment.py in src, and for the same reason: each file stays under the
test suite's own size limit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.builder import build_manifest
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _run() -> Run:
    return Run(
        id="r1",
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.RUNNING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_environment_reports_no_execution_parameters_without_a_transcript():
    manifest = build_manifest(_run(), [], _workflow(), {}, None, None)

    assert manifest.environment.cpu_threads is None
    assert manifest.environment.num_workers is None


def test_environment_reports_a_transcript_written_before_migration_0020():
    """A Transcript predating cpu_threads/num_workers must
    keep reporting None, never an invented number, the same rule
    hardware_profile_used already follows for a Transcript with nothing
    else recorded.
    """
    transcript = Transcript(
        id="t1",
        recording_id="rec1",
        language="it",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="base",
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, None, transcript)

    assert manifest.environment.cpu_threads is None
    assert manifest.environment.num_workers is None


def test_environment_reports_the_transcript_s_effective_execution_parameters():
    transcript = Transcript(
        id="t1",
        recording_id="rec1",
        language="it",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="base",
        cpu_threads=4,
        num_workers=2,
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, None, transcript)

    assert manifest.environment.cpu_threads == 4
    assert manifest.environment.num_workers == 2
