"""voxtrama.calibration.anchoring's two measures, built from a real run.

Hand-writing needs_review on an output.json would only prove the code
reads a boolean, not that this measures what engine.anchoring
decided (see calibration/anchoring.py's own docstring). So every case
here drives execute_run for real, via fakes.anchoring_run, the same way
tests/test_engine_anchoring_run.py does, and only then reads the run back.

The RunMaterialStatus cases (missing manifest, missing output, a failed
step's own row) live in test_calibration_anchoring_missing.py instead:
different question, same module under test.
"""

from __future__ import annotations

import pytest
from fakes.anchoring_run import TRANSCRIPT_TEXT, run_workflow
from sqlalchemy.orm import Session

from voxtrama.calibration.anchoring import measure_run
from voxtrama.calibration.anchoring_report import RunMaterialStatus, SkillKey
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings


def _measure(run_id: str):
    paths = get_paths(get_settings().data_dir)
    return measure_run(paths.runs_dir, run_id)


def test_a_claim_that_does_not_anchor_lands_among_needs_review(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session,
        monkeypatch,
        {"summarize": {"skill": "summarize", "output": {"claim": {"quote": "not in transcript"}}}},
    )

    report = _measure(run_id)

    assert report.status == RunMaterialStatus.MEASURED
    step = report.per_step["summarize"]
    assert (step.claims, step.needs_review) == (1, 1)
    assert step.coverage == 0.0
    skill = report.per_skill[SkillKey("summarize", "1.0.0")]
    assert skill.coverage is not None
    assert skill.coverage < 1.0


def test_a_step_with_no_claims_has_no_coverage(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session, monkeypatch, {"summarize": {"skill": "summarize", "output": {}}}
    )

    report = _measure(run_id)

    assert report.per_step["summarize"].coverage is None
    assert report.per_skill[SkillKey("summarize", "1.0.0")].coverage is None


def test_two_distinct_skills_are_not_summed_into_one_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session,
        monkeypatch,
        {
            "a": {"skill": "summarize", "output": {"claim": {"quote": TRANSCRIPT_TEXT}}},
            "b": {"skill": "extract", "output": {"claim": {"quote": "not in transcript"}}},
        },
    )

    report = _measure(run_id)

    summarize = report.per_skill[SkillKey("summarize", "1.0.0")]
    extract = report.per_skill[SkillKey("extract", "1.0.0")]
    assert (summarize.claims, summarize.needs_review) == (1, 0)
    assert (extract.claims, extract.needs_review) == (1, 1)
