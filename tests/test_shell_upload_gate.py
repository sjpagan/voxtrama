"""The home closes the file box and says what is missing, schema included.

The defect: the box accepted a file on an installation that could not
process it, and the failure only surfaced in the run. A control that is
just switched off would be half the job. The page must say **why** and
**where** it gets fixed, and that is what keeps "zero decisions before
the first success" true: the gate asks for no decision, it sends the user
to the procedure that measures and proposes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def test_the_box_is_closed_on_an_installation_that_is_not_ready(client: TestClient) -> None:
    """Controls disappear instead of being switched off.

    That is the rule in components/_buttons.scss ("a control nobody can use
    yet is not rendered at all, instead of shown disabled"), and disappearing
    is also the only way that works: "Choose file" is a <label>, and
    `disabled` on a label does not disable it (tested on screen: it still
    opened the file picker).
    """
    body = client.get("/").text

    assert "vx-gate" in body
    # The form stays but `Start job` does not. Its reasons stand in its place.
    assert "Start job" not in body


def test_it_says_what_is_missing_instead_of_only_being_off(client: TestClient) -> None:
    body = client.get("/").text

    assert "A job cannot start yet" in body


def test_it_links_to_the_step_that_fixes_it(client: TestClient) -> None:
    """A disabled control with no remedy is only half the job."""
    body = client.get("/").text

    assert "/setup/local-processing" in body


def test_the_box_is_open_once_everything_checks_out(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(
        "voxtrama.diagnostics.readiness_models.is_cached", lambda weights, models_dir: True
    )
    monkeypatch.setattr("voxtrama.db.schema_check.is_up_to_date", lambda engine: True)

    body = client.get("/").text

    assert "vx-gate" not in body
    assert "Start job" in body
    assert 'action="/jobs"' in body
