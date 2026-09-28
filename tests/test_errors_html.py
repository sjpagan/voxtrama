"""Content negotiation on a request failure: application/problem+json by
default, a page when the Accept header prefers text/html (api.error_accept,
api.error_page).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_settings
from voxtrama.config.settings import Settings
from voxtrama.db.models import Base


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def test_a_404_with_accept_html_is_a_page(client: TestClient) -> None:
    response = client.delete("/runs/no-such-run", headers={"Accept": "text/html"})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    # title and detail from the problem document, unchanged, land in the page.
    json_body = client.delete(
        "/runs/no-such-run", headers={"Accept": "application/problem+json"}
    ).json()
    assert json_body["title"] in response.text
    assert json_body["detail"] in response.text


def test_a_404_with_accept_problem_json_matches_todays_body(client: TestClient) -> None:
    today = client.delete("/runs/no-such-run")
    negotiated = client.delete("/runs/no-such-run", headers={"Accept": "application/problem+json"})

    assert today.status_code == negotiated.status_code == 404
    assert (
        today.headers["content-type"]
        == negotiated.headers["content-type"]
        == ("application/problem+json")
    )
    assert today.json() == negotiated.json()


def test_a_404_with_accept_star_star_stays_json(client: TestClient) -> None:
    response = client.delete("/runs/no-such-run", headers={"Accept": "*/*"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_a_validation_error_with_accept_html_is_a_page(client: TestClient) -> None:
    response = client.get("/jobs?cleaned=oops", headers={"Accept": "text/html"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert "cleaned" in response.text


def test_a_validation_error_with_no_accept_matches_todays_body(client: TestClient) -> None:
    today = client.get("/jobs?cleaned=oops")
    negotiated = client.get("/jobs?cleaned=oops", headers={"Accept": "application/problem+json"})

    assert today.status_code == negotiated.status_code == 422
    assert today.json()["code"] == "validation_failed"
    assert today.json() == negotiated.json()
