"""A client for the Workflows page's tests: the real shipped workflows,
a data directory of its own, and an edition that allows one custom workflow
whatever policy file this checkout carries."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.api.routes import workflow_library
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.edition.policy import EditionPolicy
from voxtrama.workflow import custom_limit


def workflows_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # save_document and document_roots read the process-wide get_settings()
    # (test_workflow_edit.py's own fixture shape), hence the env var.
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    policy = EditionPolicy(custom_workflows=1, profile_fields=frozenset())
    monkeypatch.setattr(custom_limit, "current_policy", lambda: policy)
    monkeypatch.setattr(workflow_library, "current_policy", lambda: policy)
    engine = create_engine(f"sqlite:///{tmp_path / 'workflows.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)
    get_settings.cache_clear()


def card_of(body: str, title: str) -> str:
    """The card titled `title`, from its heading to its end."""
    start = body.index(f'<h3 class="vx-wf-card__title">{title}</h3>')
    return body[start : body.index("</article>", start)]
