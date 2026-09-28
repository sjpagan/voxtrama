"""The navbar search: transcripts and job titles only."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.jobs import seed_job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.rendering.search_results import marked


@pytest.fixture
def seeded(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, object]]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'search.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    with Session(engine, expire_on_commit=False) as session:
        q3 = seed_job(session, tmp_path, "Q3 planning sync", ["Align the Roadmap now.", "Lunch?"])
        weekly = seed_job(session, tmp_path, "Weekly product sync", ["The roadmap slips."], day=2)
        seed_job(session, tmp_path, "Board prep", ["Nothing here."], day=3)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app), {"q3": q3, "weekly": weekly}


def test_results_are_grouped_by_job_newest_first(seeded) -> None:
    client, runs = seeded

    body = client.get("/search?q=roadmap").text

    assert "2 matches in" in body
    assert body.index("Weekly product sync") < body.index("Q3 planning sync")
    assert "Board prep" not in body


def test_each_occurrence_marks_the_word_and_links_to_its_line(seeded) -> None:
    client, runs = seeded

    body = client.get("/search?q=roadmap").text

    assert "<mark>Roadmap</mark>" in body
    assert f'href="/runs/{runs["q3"].id}/view#vx-transcript-row-' in body


def test_a_job_is_found_by_its_title_too(seeded) -> None:
    client, _ = seeded

    body = client.get("/search?q=board").text

    assert "Board prep" in body
    assert "Found in the job" in body


def test_percent_is_searched_as_itself_not_as_a_wildcard(seeded) -> None:
    client, _ = seeded

    assert "The search produced no results." in client.get("/search?q=%25%25").text


def test_one_character_is_not_searched(seeded) -> None:
    client, _ = seeded

    assert "Type at least two characters." in client.get("/search?q=r").text


def test_marked_splits_around_every_occurrence_ignoring_case() -> None:
    assert marked("Road, roadmap, ROAD.", "road") == [
        ("Road", True),
        (", ", False),
        ("road", True),
        ("map, ", False),
        ("ROAD", True),
        (".", False),
    ]


def test_the_field_has_a_search_button_and_a_reset(seeded) -> None:
    client, _ = seeded

    empty = client.get("/search").text
    searched = client.get("/search", params={"q": "roadmap"}).text

    assert '<button class="vx-search__submit" type="submit">' in empty
    assert 'class="vx-search__reset" type="reset"' in empty  # nothing searched: empties the field
    # A reset button would bring the searched words back; the link clears them.
    assert '<a class="vx-search__reset" href="/search"' in searched
