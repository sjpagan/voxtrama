"""Run-level choices, textually: two runs of the same workflow and audio,
with a different profile and model chosen at request time, produce two
manifests that say which choice was made, and a run that chose nothing
reports null/empty and falls back to the machine's own setting, exactly as
before run-level choices existed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.manifest.builder import build_manifest
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _run(choices: dict | None, run_id: str, label: str | None = None) -> Run:
    return Run(
        id=run_id,
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.RUNNING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        choices=choices,
        label=label,
    )


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="The same workflow both runs share.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def _recording() -> Recording:
    """The same audio both runs share: what differs between them is only the choice."""
    return Recording(
        id="rec1",
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=42.0,
        media_format="wav",
    )


def test_two_runs_of_the_same_workflow_and_audio_report_their_own_choices():
    workflow = _workflow()
    recording = _recording()

    high = build_manifest(
        _run({"hardware_profile": "high", "generative_model": "model-a"}, "r-high"),
        [],
        workflow,
        {},
        recording,
        None,
    )
    low = build_manifest(
        _run({"hardware_profile": "low", "generative_model": "model-b"}, "r-low"),
        [],
        workflow,
        {},
        recording,
        None,
    )

    assert (high.choices.hardware_profile, high.choices.generative_model) == ("high", "model-a")
    assert (low.choices.hardware_profile, low.choices.generative_model) == ("low", "model-b")
    # environment_info's own field, not just choices: the requested profile
    # a reader sees there must match what was chosen.
    assert high.environment.hardware_profile_requested == "high"
    assert low.environment.hardware_profile_requested == "low"


def test_a_run_that_chose_nothing_reports_null_and_falls_back_to_the_machine_setting():
    manifest = build_manifest(_run(None, "r-none"), [], _workflow(), {}, _recording(), None)

    assert manifest.choices.hardware_profile is None
    assert manifest.choices.generative_model is None
    assert manifest.choices.step_skills == {}
    # RunChoices() (every field None or empty) is what "chose nothing"
    # reads as (workflow.choices' own docstring); the manifest must still
    # report what the run used, which is the machine's setting.
    assert manifest.environment.hardware_profile_requested == get_settings().hardware_profile


def test_178_choices_and_the_run_s_own_label_reach_the_manifest():
    choices = {"diarize": False, "max_speakers": 2, "cores_per_chunk": 3, "parallel_chunks": 1}
    manifest = build_manifest(
        _run(choices, "r-178", label="Call with Mario"), [], _workflow(), {}, _recording(), None
    )

    assert manifest.run.label == "Call with Mario"
    assert manifest.choices.diarize is False
    assert manifest.choices.max_speakers == 2
    assert manifest.choices.cores_per_chunk == 3
    assert manifest.choices.parallel_chunks == 1
