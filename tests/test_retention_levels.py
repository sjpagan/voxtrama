"""The three retention levels, and where each is set."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.api.routes.job_choices import JobForm, job_choices
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.engine.skill_catalog import load_named_skill_file
from voxtrama.setup.installation import (
    InstallationConfig,
    read_installation_config,
    write_installation_config,
)
from voxtrama.workflow.retention import policy_days, strictest, workflow_days


def test_the_strictest_level_wins_and_says_which_it_is() -> None:
    assert strictest(None, None, None) is None
    assert strictest(90, 30, None).level == "workflow"
    assert strictest(10, None, 7).days == 7
    assert strictest(7, None, 30).level == "installation"


def test_a_workflow_s_limit_is_the_shortest_its_skills_declare() -> None:
    assert policy_days("follows_recording") is None and policy_days("30d") == 30
    assert workflow_days(["follows_recording", "30d", "7d"]) == 7
    assert workflow_days(["follows_recording"]) is None


def test_a_skill_can_only_declare_a_policy_that_means_something() -> None:
    skill = load_named_skill_file("summarize").skill
    fields = skill.model_dump(exclude={"deterministic"})

    for policy in ("7d", "follows_recording"):
        type(skill).model_validate({**fields, "retention_policy": policy})
    with pytest.raises(ValidationError):
        type(skill).model_validate({**fields, "retention_policy": "delete_after_run"})


def test_the_job_s_own_limit_is_a_choice_of_the_run(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert job_choices(JobForm(retention_days="7"), settings).retention_days == 7
    assert job_choices(JobForm(), settings).retention_days is None


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


def _configured(tmp_path: Path) -> None:
    config = InstallationConfig(cores_per_chunk=2, parallel_chunks=2)
    write_installation_config(tmp_path, config)


def test_the_installation_limit_is_set_from_settings_and_can_be_taken_off(client, tmp_path) -> None:
    _configured(tmp_path)

    client.post("/setup/retention", data={"retention_days": "30"}, follow_redirects=False)
    assert read_installation_config(tmp_path).retention_days == 30
    client.post("/setup/retention", data={"retention_days": "12345"}, follow_redirects=False)
    assert read_installation_config(tmp_path).retention_days == 30
    client.post("/setup/retention", data={"retention_days": ""}, follow_redirects=False)
    assert read_installation_config(tmp_path).retention_days is None


def test_the_job_form_offers_only_limits_shorter_than_the_installation_s(client, tmp_path) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(cores_per_chunk=2, parallel_chunks=2, retention_days=30)
    )

    body = client.get("/").text

    assert '<option value="" selected>30 days</option>' in body
    assert '<option value="7"' in body and '<option value="90"' not in body
