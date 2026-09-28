"""Every folder of domain documents reaches the places that have to carry it.

A workflow or a skill file is found by looking under the working directory
In the image that is /app, and the package's own copy is no help
once pip has installed it into site-packages, where neither folder sits beside
it. So a folder that the Dockerfile does not copy simply does not exist at
runtime. That is what once happened to skills/: the image had no
generative skills at all, and every workflow naming one failed with "unknown
skill", while every test kept passing because from a checkout the documents are
found by a different root.

This is a packaging test, not a unit test: it reads the Dockerfile as text
because that is where the mistake lives. It cannot catch a folder that is
copied but empty: the tests of each document type cover that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from voxtrama.workflow.document import DOMAIN_DOCUMENT_FOLDERS

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("folder", DOMAIN_DOCUMENT_FOLDERS)
def test_the_image_carries_every_domain_document_folder(folder: str) -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()

    assert re.search(rf"^COPY {folder}\b", dockerfile, re.MULTILINE), (
        f"the Dockerfile never copies {folder}/, so the image will not have it: "
        f"a document living there is unreachable at runtime"
    )


@pytest.mark.parametrize("folder", DOMAIN_DOCUMENT_FOLDERS)
def test_every_domain_document_folder_exists_in_the_repository(folder: str) -> None:
    """A folder declared and absent would make the COPY above fail the build."""
    assert (REPO_ROOT / folder).is_dir(), f"{folder}/ is declared but not in the repository"


def test_the_declared_folders_are_the_ones_the_code_actually_looks_in() -> None:
    """The constant is only useful if nothing looks somewhere it does not name.

    Without this, a third document type could call document_roots("presets")
    without touching DOMAIN_DOCUMENT_FOLDERS, and the test above would keep
    passing while the image silently lacked the folder, the same shape as skills/.
    """
    src = REPO_ROOT / "src" / "voxtrama"
    used = {
        match
        for path in src.rglob("*.py")
        for match in re.findall(r'document_roots\(\s*"([^"]+)"', path.read_text())
    }

    assert used <= set(DOMAIN_DOCUMENT_FOLDERS), (
        f"looked up but not declared in DOMAIN_DOCUMENT_FOLDERS: "
        f"{sorted(used - set(DOMAIN_DOCUMENT_FOLDERS))}, "
        f"so nothing guarantees the image carries them"
    )
