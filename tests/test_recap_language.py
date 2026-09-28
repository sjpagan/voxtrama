"""The language the recap is written in is the job's choice."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.api.routes.job_choices import JobForm, job_choices
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.engine.generative_windows import output_language
from voxtrama.manifest.choices import choices_info
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.skill import SAME_AS_AUDIO


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


def test_the_form_starts_from_the_browser_s_language(client) -> None:
    body = client.get("/", headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"}).text

    assert '<option value="it" selected>Italiano</option>' in body
    assert "Same as the audio" in body


def test_a_browser_in_a_language_not_offered_gets_english(client) -> None:
    body = client.get("/", headers={"Accept-Language": "ja"}).text

    assert '<option value="en" selected>English</option>' in body


def test_the_choice_is_the_run_s_and_reaches_the_manifest(tmp_path) -> None:
    choices = job_choices(JobForm(output_language="it"), Settings(data_dir=tmp_path))

    assert choices.output_language == "it"
    assert choices_info(choices).output_language == "it"
    assert job_choices(JobForm(), Settings(data_dir=tmp_path)).output_language is None


def test_the_prompt_is_told_the_chosen_language_over_the_audio_s() -> None:
    skill = SimpleNamespace(output_language=SAME_AS_AUDIO)
    transcript = SimpleNamespace(language="en")

    assert output_language(skill, transcript, "it") == "Italian"
    assert output_language(skill, transcript, None) == "English"


def test_same_as_the_audio_names_the_language_not_its_code() -> None:
    """ "written in it" read as the English pronoun, so an Italian
    recording got an English recap. The prompt must say "Italian"."""
    skill = SimpleNamespace(output_language=SAME_AS_AUDIO)
    italian = SimpleNamespace(language="it")

    assert output_language(skill, italian) == "Italian"
    assert output_language(SimpleNamespace(output_language="de"), italian) == "German"
    assert output_language(skill, SimpleNamespace(language="sw")) == "sw"


def test_a_code_that_is_not_a_language_is_refused() -> None:
    with pytest.raises(ValueError):
        RunChoices(output_language="italian")


def test_changing_the_language_reruns_the_model_steps_not_the_transcription() -> None:
    from voxtrama.engine.step_hashing import _choices_read_by

    context = SimpleNamespace(choices=RunChoices(output_language="it"), kept_local={})

    assert (
        _choices_read_by(SimpleNamespace(id="s", skill="summarize"), context)["output_language"]
        == "it"
    )
    assert "output_language" not in _choices_read_by(
        SimpleNamespace(id="t", skill="transcribe"), context
    )
