"""A concluded job with a short two-speaker conversation.

fakes/run_result.py seeds one segment; the job view's own tests need
turns (consecutive segments of one speaker, pauses between them) and a
recap with more than one kind, so this seeds those, through the
same app and manifest helpers.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from fakes.run_result import insert_run, write_manifest_and_output
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.db.models.transcript import Segment, Transcript

# (start, end, speaker, text): Alex twice without a pause (one turn),
# Taylor, then Alex again after a 6 s silence (a second turn of Alex's
# own only once the pause is under the threshold).
CONVERSATION = [
    (0.0, 4.0, "spk0", "Thanks for making time today."),
    (4.2, 8.0, "spk0", "Let's review the roadmap."),
    (8.0, 12.0, "spk1", "The roadmap needs owners."),
    (12.0, 15.0, "spk0", "Agreed, owners by Friday."),
    (21.0, 24.0, "spk0", "One more thing on the migration."),
]

PRODUCED = {
    "summarize": {
        "key_points": [
            {
                "text": "The roadmap needs owners.",
                "quote": "x",
                "evidence": {"start": 8.0, "end": 12.0},
                "needs_review": False,
            },
        ]
    },
    "extract_decisions": {
        "decisions": [
            {
                "decision": "Owners by Friday.",
                "quote": "x",
                "evidence": {"start": 12.0, "end": 15.0},
                "needs_review": False,
            },
            {
                "decision": "Revisit next month.",
                "quote": "x",
                "evidence": None,
                "needs_review": True,
            },
        ]
    },
}


def _step(run_id: str, step_id: str, position: int) -> RunStep:
    return RunStep(
        run_id=run_id,
        step_id=step_id,
        skill=step_id,
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=position,
        attempts=1,
        model="llama3.1:8b",
    )


def seed_concluded_job(engine: Engine, tmp_path: Path, run_id: str) -> None:
    """Run, Recording, Transcript and the manifest/output pair of one concluded job."""
    steps = [_step(run_id, "summarize", 0), _step(run_id, "extract_decisions", 1)]
    run = insert_run(engine, run_id, "meeting-decisions", steps[0])
    with Session(engine) as session:
        session.add(
            Recording(
                id=f"rec-{run_id}",
                original_filename="sync.wav",
                stored_path="x",
                content_sha256="b" * 64,
                duration_seconds=24.0,
                media_format="wav",
            )
        )
        transcript = Transcript(
            id=f"t-{run_id}",
            recording_id=f"rec-{run_id}",
            language="en",
            model_name="whisper",
            model_revision="v1",
            hardware_profile="low",
            produced_by_run_id=run_id,
        )
        transcript.segments = [
            Segment(start=s, end=e, speaker_label=who, text=text, confidence=1.0)
            for s, e, who, text in CONVERSATION
        ]
        session.add(transcript)
        session.commit()
    write_manifest_and_output(tmp_path, run, steps, PRODUCED)
