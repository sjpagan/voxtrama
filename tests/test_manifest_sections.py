"""build_manifest's run-level sections: languages and input.

Split from test_manifest_builder.py, which covers the per-step section.
Same split as sections.py/builder.py in src, and for the same reason:
each file stays under the test suite's own size limit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.builder import build_manifest
from voxtrama.manifest.schema import LanguageProvenance
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


def test_languages_are_not_recorded_without_a_transcript():
    manifest = build_manifest(_run(), [], _workflow(), {}, None, None)

    for language in (
        manifest.languages.interface,
        manifest.languages.audio,
        manifest.languages.output,
    ):
        assert language.value is None
        assert language.provenance == LanguageProvenance.NOT_RECORDED


def test_audio_language_is_detected_once_a_transcript_exists():
    transcript = Transcript(
        id="t1",
        recording_id="rec1",
        language="it",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="base",
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, None, transcript)

    assert manifest.languages.audio.value == "it"
    assert manifest.languages.audio.provenance == LanguageProvenance.DETECTED
    # Neither of these is resolved anywhere in the engine yet (the manifest
    # ships, not that resolution): still honest even once audio is known.
    assert manifest.languages.interface.provenance == LanguageProvenance.NOT_RECORDED
    assert manifest.languages.output.provenance == LanguageProvenance.NOT_RECORDED


def test_input_reflects_the_recording_when_there_is_one():
    recording = Recording(
        id="rec1",
        original_filename="meeting.wav",
        stored_path="recordings/rec1/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=12.3456,
        media_format="wav",
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, recording, None)

    assert manifest.input is not None
    assert manifest.input.recording_id == "rec1"
    assert manifest.input.duration_seconds == 12.346


def test_input_is_absent_without_a_recording():
    manifest = build_manifest(_run(), [], _workflow(), {}, None, None)

    assert manifest.input is None


def test_input_provenance_is_local_file_without_a_source_url():
    """Derived from source_url, not a stored flag."""
    recording = Recording(
        id="rec1",
        original_filename="meeting.wav",
        stored_path="recordings/rec1/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, recording, None)

    assert manifest.input.provenance == "local_file"
    assert manifest.input.source_url is None
    assert manifest.input.source_title is None


def test_input_provenance_is_url_when_a_source_url_is_set():
    recording = Recording(
        id="rec1",
        original_filename="clip.opus",
        stored_path="recordings/rec1/clip.opus",
        content_sha256="0" * 64,
        duration_seconds=1.0,
        media_format="opus",
        source_title="A Creative Commons clip",
        source_url="https://example.com/watch?v=abc123",
    )

    manifest = build_manifest(_run(), [], _workflow(), {}, recording, None)

    assert manifest.input.provenance == "url"
    assert manifest.input.source_url == "https://example.com/watch?v=abc123"
    assert manifest.input.source_title == "A Creative Commons clip"


def test_run_is_final_when_cancelled_or_interrupted():
    """The defect this closes: manifest.run.final used to read from
    FINAL_RUN_STATES, a hand-written set that never included `cancelled`,
    so a cancelled or interrupted run's manifest never became final,
    even though a failed run's manifest is the most important one.
    """
    for state in (RunState.CANCELLED, RunState.INTERRUPTED):
        run = Run(
            id="r1",
            workflow_name="demo",
            workflow_version="1.0.0",
            state=state,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        manifest = build_manifest(run, [], _workflow(), {}, None, None)
        assert manifest.run.final is True
