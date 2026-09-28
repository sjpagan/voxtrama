"""Tests for rendering.run_output.output_items.

Manifest built through manifest.builder.build_manifest, the same assembly
write_run_manifest uses (test_runs_api_evidence.py's own convention).
Hand-rolling every nested manifest section here would only risk drifting
from what a real manifest.json contains.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.manifest.builder import build_manifest
from voxtrama.manifest.output import RunOutput
from voxtrama.rendering.run_output import output_items


def _run(workflow_name: str) -> Run:
    return Run(
        id="run-1",
        workflow_name=workflow_name,
        workflow_version="2.0.0",
        state=RunState.SUCCEEDED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _step(step_id: str, skill: str, model: str | None) -> RunStep:
    return RunStep(
        run_id="run-1",
        step_id=step_id,
        skill=skill,
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
        model=model,
    )


def test_a_decision_becomes_one_card_with_its_own_provenance() -> None:
    manifest = build_manifest(
        _run("meeting-decisions"),
        [_step("extract_decisions", "extract_decisions", "llama3.1:8b")],
        None,
        {},
        None,
        None,
    )
    output = RunOutput(
        run_id="run-1",
        steps={
            "extract_decisions": {
                "decisions": [
                    {
                        "decision": "Ship the new onboarding flow on 7 October.",
                        "quote": "we'll ship it on 7 october",
                        "evidence": {"start": 754.0, "end": 761.0},
                        "needs_review": False,
                    }
                ]
            }
        },
    )

    items = output_items(manifest, output)

    assert len(items) == 1
    item = items[0]
    assert item.kind == "decision"
    assert item.heading is None
    assert item.text == "Ship the new onboarding flow on 7 October."
    assert item.needs_review is False
    assert item.evidence_label == "12:34-12:41"
    assert item.provenance.workflow == "meeting-decisions"
    assert item.provenance.skill == "extract_decisions"
    assert item.provenance.model == "llama3.1:8b"


def test_a_concept_carries_its_own_name_as_the_heading() -> None:
    manifest = build_manifest(
        _run("lesson-companion"),
        [_step("extract_concepts", "extract_concepts", None)],
        None,
        {},
        None,
        None,
    )
    output = RunOutput(
        run_id="run-1",
        steps={
            "extract_concepts": {
                "concepts": [
                    {
                        "concept": "Entropy",
                        "definition": "A measure of disorder.",
                        "quote": "entropy is a measure of disorder",
                        "evidence": None,
                        "needs_review": True,
                    }
                ]
            }
        },
    )

    items = output_items(manifest, output)

    assert items[0].heading == "Entropy"
    assert items[0].text == "A measure of disorder."
    assert items[0].needs_review is True
    assert items[0].evidence_label is None
    assert items[0].provenance.model is None


def test_a_step_with_no_claim_shaped_output_contributes_nothing() -> None:
    manifest = build_manifest(
        _run("transcribe-only"), [_step("diarize", "diarize", None)], None, {}, None, None
    )
    output = RunOutput(run_id="run-1", steps={"diarize": {"speaker_estimate": 2}})

    assert output_items(manifest, output) == ()
