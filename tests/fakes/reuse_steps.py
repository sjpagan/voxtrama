"""Shared fakes for the reuse tests: transcribe/diarize/summarize built-ins that count calls.

Split out of test_engine_reuse.py so both it and test_engine_reuse_no_match.py
can drive the same three-step shape without each carrying its own copy.
That is the reason for every other split in this repo, applied to two
test files instead of two src ones. Mirrors fakes.workflow.fake_skill, not
real transcription or diarization: what the reuse tests exercise is the
engine's own reuse decision, not either library.
"""

from __future__ import annotations

import pytest

from fakes.workflow import fake_skill
from voxtrama.db.models.transcript import Transcript
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress import record_provenance
from voxtrama.workflow.definition import Step, Workflow


def workflow(summarize_skill: str, transcribe_skill: str = "t") -> Workflow:
    """Steps t (transcribe-like), d (diarize-like), s (summarize-like); t and s named by choice.

    `transcribe_skill` defaults to "t" so every test that only varies
    the last step keeps calling this positionally. The cascade test
    (test_engine_superseded.py) is the one caller that passes "t2" here,
    to redo the first step under a different skill without touching the
    workflow's shape.
    """
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="t", skill=transcribe_skill, skill_version="1.0.0"),
            Step(id="d", skill="d", skill_version="1.0.0", depends_on=["t"]),
            Step(id="s", skill=summarize_skill, skill_version="1.0.0", depends_on=["d"]),
        ],
    )


def _fake_transcribe(calls: dict[str, int], key: str = "t"):
    """A fake transcribe step: writes a real Transcript row, and its own provenance, onto `ctx`.

    `key` counts this call under a name of its own in `calls`: "t2" for
    the second transcribe skill test_engine_superseded.py registers below,
    so a run redoing transcription under a different skill is still
    visibly counted apart from the first one.
    """

    def _t(ctx: ExecutionContext) -> dict:
        calls[key] += 1
        transcript = Transcript(
            recording_id=ctx.recording.id,
            language="en",
            model_name="fake-asr",
            model_revision="rev-1",
            hardware_profile="base",
        )
        ctx.session.add(transcript)
        ctx.session.flush()
        ctx.transcript = transcript
        record_provenance(
            ctx.session,
            ctx.step_rows["t"],
            model="fake-asr",
            model_revision="rev-1",
            provider="local",
            host=None,
            profile_check_skipped=False,
        )
        return {"transcript_id": transcript.id}

    return _t


def install(monkeypatch: pytest.MonkeyPatch, calls: dict[str, int]) -> None:
    """Fake transcribe/diarize/summarize built-ins, each counting its own calls in `calls`.

    Registers a second transcribe skill, "t2", alongside "t": both write a
    genuinely new Transcript, so a workflow that names "t2" for its first
    step (test_engine_superseded.py's cascade test) redoes transcription
    rather than reusing "t"'s. Unused by every other reuse test, which
    never names "t2" in a workflow.
    """

    def _d(ctx: ExecutionContext) -> dict:
        calls["d"] += 1
        assert ctx.transcript is not None, "diarize needs a transcript, reused or not"
        return {"transcript_id": ctx.transcript.id, "speaker_estimate": 1}

    def _s(name: str):
        def _run(ctx: ExecutionContext) -> dict:
            calls[name] += 1
            assert ctx.transcript is not None, "summarize needs a transcript, reused or not"
            return {"summary": name}

        return _run

    steps = {
        "t": _fake_transcribe(calls, "t"),
        "t2": _fake_transcribe(calls, "t2"),
        "d": _d,
        "s1": _s("s1"),
        "s2": _s("s2"),
    }
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", steps)
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {name: {"1.0.0": fake_skill(name)} for name in ("t", "t2", "d", "s1", "s2")},
    )
