"""`voxtrama calibrate --run`: the branch calibrate.py delegates to calibrate_run.py.

The measures themselves are test_calibration_anchoring.py's job. This only
checks the command finds a run (or names what is missing, same
RunMaterialStatus discipline as calibrate.py's own DatasetStatus cases)
and prints what calibration.anchoring computed, at exit code 0 either way,
the same convention as every other case of `voxtrama calibrate`.
"""

from __future__ import annotations

import pytest
from fakes.anchoring_run import run_workflow
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from voxtrama.cli.main import app

runner = CliRunner()


def test_a_run_that_does_not_exist_names_its_manifest_missing() -> None:
    result = runner.invoke(app, ["calibrate", "--run", "no-such-run"])

    assert result.exit_code == 0
    assert "manifest.json" in result.output


def test_a_run_reports_its_unanchored_claim_by_step_and_by_skill(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session,
        monkeypatch,
        {
            "summarize": {
                "skill": "summarize",
                "output": {"claim": {"quote": "not in the transcript"}},
            }
        },
    )

    result = runner.invoke(app, ["calibrate", "--run", run_id])

    assert result.exit_code == 0
    assert "by step:" in result.output
    assert "summarize" in result.output
    assert "needs_review: 1" in result.output
    assert "by skill:" in result.output
    assert "summarize@1.0.0" in result.output


def test_a_failed_step_is_named_as_skipped_not_left_off_the_report(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session, monkeypatch, {"summarize": {"skill": "summarize", "fails": True}}
    )

    result = runner.invoke(app, ["calibrate", "--run", run_id])

    assert result.exit_code == 0
    assert "skipped" in result.output
    assert "summarize" in result.output
