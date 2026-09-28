"""The upload gate: when the box opens, and what it says when it does not.

The defect these tests prevent: the home page accepted a file on an
installation with no model, no resolvable profile and no writable folder.
The upload succeeded and the failure surfaced in the run, where it is
harder to read. The extreme case: eight minutes of transcription
before dying on a missing table.
"""

from __future__ import annotations

import pytest

from voxtrama.diagnostics.readiness_state import (
    LocalProcessingCheck,
    ModelsReadyCheck,
    PrivateStorageCheck,
    Readiness,
    ReadinessReport,
    SchemaCheck,
)
from voxtrama.rendering.upload_gate import upload_gate


def _report(
    local: Readiness = Readiness.READY,
    models: Readiness = Readiness.READY,
    storage: Readiness = Readiness.READY,
) -> ReadinessReport:
    return ReadinessReport(
        local_processing=LocalProcessingCheck(state=local, reason="local", hardware_profile="base"),
        models_ready=ModelsReadyCheck(state=models, reason="models", model="medium"),
        private_storage=PrivateStorageCheck(state=storage, reason="storage", free_disk_bytes=1),
    )


def _schema(state: Readiness = Readiness.READY) -> SchemaCheck:
    return SchemaCheck(state=state, reason="schema")


def test_everything_ready_opens_the_box() -> None:
    gate = upload_gate(_report(), _schema())

    assert gate.allowed
    assert gate.blockers == []


@pytest.mark.parametrize("missing", ["local", "models", "storage"])
def test_any_state_not_ready_closes_the_box(missing: str) -> None:
    gate = upload_gate(_report(**{missing: Readiness.NOT_READY}), _schema())

    assert not gate.allowed
    assert len(gate.blockers) == 1


def test_unknown_closes_the_box_exactly_like_not_ready() -> None:
    """An unknown state does not count as green.

    A value nobody managed to read is not a value anyone has verified, and
    treating it as one would bring back the very upload that succeeds on an
    installation that cannot handle it.
    """
    gate = upload_gate(_report(storage=Readiness.UNKNOWN), _schema())

    assert not gate.allowed
    assert [blocker.key for blocker in gate.blockers] == ["private_storage"]


def test_a_schema_behind_the_code_closes_the_box_too() -> None:
    """The same family as the other three, and it closes the same way."""
    gate = upload_gate(_report(), _schema(Readiness.NOT_READY))

    assert not gate.allowed
    assert [blocker.key for blocker in gate.blockers] == ["schema"]


def test_every_blocker_but_the_schema_points_at_the_step_that_fixes_it() -> None:
    """A schema that is behind cannot be fixed from a page: it needs a rebuild.

    The other three each have a wizard step that resolves them, and that is
    why no decision is required up front: the gate does not ask for a decision, it sends the
    user to where things are measured and proposed.
    """
    gate = upload_gate(
        _report(Readiness.NOT_READY, Readiness.NOT_READY, Readiness.NOT_READY),
        _schema(Readiness.NOT_READY),
    )

    fixes = {blocker.key: blocker.fix_href for blocker in gate.blockers}
    assert fixes["local_processing"] == "/setup/local-processing"
    assert fixes["models_ready"] == "/setup/local-processing"
    assert fixes["private_storage"] == "/setup/private-storage"
    assert fixes["schema"] is None


def test_the_reason_each_check_gave_survives_into_the_blocker() -> None:
    """A "not ready" that names no state sends the reader to look in four places."""
    report = ReadinessReport(
        local_processing=LocalProcessingCheck(
            state=Readiness.NOT_READY,
            reason="profile 'turbo' is not one we run",
            hardware_profile="turbo",
        ),
        models_ready=ModelsReadyCheck(state=Readiness.READY, reason="", model="medium"),
        private_storage=PrivateStorageCheck(state=Readiness.READY, reason="", free_disk_bytes=1),
    )

    gate = upload_gate(report, _schema())

    assert gate.blockers[0].reason == "profile 'turbo' is not one we run"
