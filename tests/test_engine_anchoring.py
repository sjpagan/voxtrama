"""anchor_output's own rules: unit-level, no session.

anchor_output takes a Skill, a Transcript and an output dict (no
ExecutionContext, no models, no audio), so these build a Transcript by
hand, the way tests/test_engine_validation.py's pattern note suggests, and
call it directly. Engine wiring (failure propagation, the manifest on
disk) is covered separately in test_engine_anchoring_run.py.
"""

from __future__ import annotations

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.anchoring import anchor_output
from voxtrama.manifest.evidence import ClaimCount
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _segment(start: float, end: float, text: str) -> Segment:
    return Segment(start=start, end=end, text=text, confidence=1.0)


def _transcript(*segments: Segment) -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = list(segments)
    return transcript


def _skill(model_class: ModelClass, evidence_required: bool = False) -> Skill:
    return Skill(
        name="fake",
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=model_class,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=evidence_required,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def test_generative_claim_citing_a_missing_passage_needs_review():
    transcript = _transcript(_segment(0.0, 2.0, "hello there"))
    claim = {"quote": "nothing like this was said"}

    count = anchor_output(_skill(ModelClass.GENERATIVE), transcript, {"claim": claim})

    assert count.claims == 1 and count.needs_review == 1
    assert claim == {"quote": "nothing like this was said", "evidence": None, "needs_review": True}


def test_generative_claim_citing_a_real_passage_anchors():
    transcript = _transcript(
        _segment(0.0, 2.0, "hello there"), _segment(2.0, 4.0, "general kenobi")
    )
    claim = {"quote": "hello there"}

    anchor_output(_skill(ModelClass.GENERATIVE), transcript, {"claim": claim})

    assert claim["needs_review"] is False
    assert claim["evidence"] == {"start": 0.0, "end": 2.0}


def test_generative_false_declared_interval_is_discarded_for_the_real_one():
    transcript = _transcript(
        _segment(0.0, 2.0, "hello there"), _segment(2.0, 4.0, "general kenobi")
    )
    # A generative model asked to cite a timestamp invents a plausible one:
    # here it names the second segment for a quote in the first.
    claim = {"quote": "hello there", "evidence": {"start": 2.0, "end": 4.0}}

    anchor_output(_skill(ModelClass.GENERATIVE), transcript, {"claim": claim})

    assert claim["evidence"] == {"start": 0.0, "end": 2.0}
    assert claim["needs_review"] is False


def test_extractive_interval_that_does_not_cover_the_quote_needs_review():
    transcript = _transcript(
        _segment(0.0, 2.0, "hello there"), _segment(2.0, 4.0, "general kenobi")
    )
    claim = {"quote": "hello there", "evidence": {"start": 2.0, "end": 4.0}}

    anchor_output(_skill(ModelClass.EXTRACTIVE), transcript, {"claim": claim})

    assert claim == {"quote": "hello there", "evidence": None, "needs_review": True}


def test_extractive_interval_that_covers_the_quote_stays_anchored():
    transcript = _transcript(_segment(0.0, 2.0, "hello there"))
    claim = {"quote": "hello there", "evidence": {"start": 0.0, "end": 2.0}}

    anchor_output(_skill(ModelClass.EXTRACTIVE), transcript, {"claim": claim})

    assert claim["evidence"] == {"start": 0.0, "end": 2.0}
    assert claim["needs_review"] is False


def test_a_quote_occurring_twice_is_ambiguous_and_not_anchored():
    transcript = _transcript(_segment(0.0, 1.0, "yes"), _segment(5.0, 6.0, "yes"))
    claim = {"quote": "yes"}

    anchor_output(_skill(ModelClass.GENERATIVE), transcript, {"claim": claim})

    assert claim["needs_review"] is True
    assert claim["evidence"] is None


def test_a_claim_nested_inside_a_list_inside_a_dict_is_found_and_anchored():
    transcript = _transcript(_segment(0.0, 2.0, "hello there"))
    output = {"section": {"items": [{"label": "greeting", "quote": "hello there"}]}}

    count = anchor_output(_skill(ModelClass.GENERATIVE), transcript, output)

    claim = output["section"]["items"][0]
    assert count.claims == 1
    assert claim["needs_review"] is False
    assert claim["evidence"] == {"start": 0.0, "end": 2.0}


def test_without_a_transcript_nothing_anchors():
    claim = {"quote": "hello there"}

    count = anchor_output(_skill(ModelClass.EXTRACTIVE), None, {"claim": claim})

    assert count == ClaimCount(claims=1, needs_review=1)
    assert claim["needs_review"] is True and claim["evidence"] is None
