"""voxtrama.calibration.anchoring's RunMaterialStatus cases.

Split from test_calibration_anchoring.py: that file covers the measure
itself, on a run that fully succeeded. This one covers everything
measure_run reports instead of a measure: a run not on disk at all, one
with a manifest but no output.json yet, and a run whose one step failed,
which must be named in skipped_steps rather than silently absent.
"""

from __future__ import annotations

import pytest
from fakes.anchoring_run import run_workflow
from sqlalchemy.orm import Session

from voxtrama.calibration.anchoring import measure_run
from voxtrama.calibration.anchoring_report import RunMaterialStatus
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.manifest.output import output_path


def _measure(run_id: str):
    paths = get_paths(get_settings().data_dir)
    return measure_run(paths.runs_dir, run_id)


def test_a_run_that_does_not_exist_reports_its_manifest_missing(tmp_path) -> None:
    report = measure_run(tmp_path, "no-such-run")

    assert report.status == RunMaterialStatus.MANIFEST_MISSING


def test_a_run_with_a_manifest_but_no_output_yet_reports_that(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session, monkeypatch, {"summarize": {"skill": "summarize", "output": {}}}
    )
    output_path(get_paths(get_settings().data_dir).runs_dir, run_id).unlink()

    report = _measure(run_id)

    assert report.status == RunMaterialStatus.OUTPUT_MISSING


def test_a_failed_steps_own_row_is_named_in_skipped_steps_not_silently_absent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = run_workflow(
        db_session, monkeypatch, {"summarize": {"skill": "summarize", "fails": True}}
    )

    report = _measure(run_id)

    assert report.status == RunMaterialStatus.MEASURED
    assert report.skipped_steps == ("summarize",)
    assert "summarize" not in report.per_step
