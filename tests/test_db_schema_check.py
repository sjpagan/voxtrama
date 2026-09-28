"""The database schema among the readiness states.

The defect behind this module: a run transcribed for eight minutes, then
died on `no such table: speaker_name`, because the database was at Alembic
revision 0020 and the code wanted 0021. `is_up_to_date` already knew, and
only `/health` ever asked it.

The verdict is core data (diagnostics.readiness_state.SchemaCheck). The
read is an adapter (db.schema_check): it opens a connection, and that line
is kept clean.
"""

from __future__ import annotations

import pytest

from voxtrama.db import schema_check as schema_check_module
from voxtrama.db.migrations_state import MigrationsStateError
from voxtrama.db.schema_check import SCHEMA_FIX, check_schema
from voxtrama.diagnostics.readiness_state import Readiness


def test_a_database_at_head_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema_check_module, "is_up_to_date", lambda engine: True)

    assert check_schema(object()).state is Readiness.READY


def test_a_database_behind_the_code_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema_check_module, "is_up_to_date", lambda engine: False)

    check = check_schema(object())

    assert check.state is Readiness.NOT_READY


def test_the_reason_says_what_to_do_not_only_what_is_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«database is not at Alembic's head revision» is true and useless.

    Whoever reads it does not know they must rebuild EVERY service: rebuilding
    two of three leaves the `migrate` image behind, which is how the defect
    happened.
    """
    monkeypatch.setattr(schema_check_module, "is_up_to_date", lambda engine: False)

    assert SCHEMA_FIX in check_schema(object()).reason
    assert "docker compose build" in check_schema(object()).reason


def test_a_revision_that_cannot_be_read_is_unknown_not_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNKNOWN, never a plausible False: to a person those are two different sentences."""

    def _raise(engine: object) -> bool:
        raise MigrationsStateError("no such file")

    monkeypatch.setattr(schema_check_module, "is_up_to_date", _raise)

    check = check_schema(object())

    assert check.state is Readiness.UNKNOWN
    assert "no such file" in check.reason
