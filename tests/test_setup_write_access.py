"""Settings › Data & privacy: who writes the files, and a real write per folder."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from test_setup_privacy_page import _client

from voxtrama.config.settings import Settings
from voxtrama.diagnostics import write_access as wa


def test_every_folder_that_exists_is_written_and_passes(tmp_path, monkeypatch) -> None:
    (tmp_path / "recordings").mkdir()
    (tmp_path / "runs").mkdir()
    monkeypatch.setenv("VOXTRAMA_RUN_AS_UID", "1000")
    monkeypatch.delenv("VOXTRAMA_RUN_AS_GID", raising=False)

    access = wa.write_access(tmp_path)

    assert [f.key for f in access.folders] == ["data", "recordings", "runs"]
    assert all(f.ok for f in access.folders)
    assert access.runs_as.uid == os.getuid()
    assert (access.run_as_uid, access.run_as_gid) == ("1000", None)
    assert not list(tmp_path.rglob(".voxtrama-write-probe"))


def test_a_missing_data_folder_says_so(tmp_path) -> None:
    check = wa.write_access(tmp_path / "gone").folders[0]

    assert (check.ok, check.cause) == (False, wa.MISSING)


@pytest.mark.parametrize(
    ("code", "owner_uid", "cause"),
    [
        (errno.EROFS, 0, wa.READ_ONLY),
        (errno.EACCES, 4242, wa.OWNER),
        (errno.EACCES, None, wa.PERMISSIONS),
        (errno.ENOSPC, 0, wa.OTHER),
    ],
)
def test_a_refused_write_names_its_cause(tmp_path, monkeypatch, code, owner_uid, cause) -> None:
    runs_as = wa.Account(os.getuid(), os.getgid(), None)
    owner = wa.Account(runs_as.uid if owner_uid is None else owner_uid, 4242, None)
    monkeypatch.setattr(wa, "_owner", lambda path: owner)

    def refuse(self: Path, data: bytes) -> int:
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(Path, "write_bytes", refuse)

    check = wa.check_folder("data", tmp_path, runs_as)

    assert (check.ok, check.cause) == (False, cause)


def test_the_page_shows_the_identities_and_the_fix(tmp_path, monkeypatch) -> None:
    owner = wa.Account(4242, 4343, "someone")
    monkeypatch.setattr(wa, "_owner", lambda path: owner)
    real = Path.write_bytes

    def refuse(self: Path, data: bytes) -> int:
        if self.name == ".voxtrama-write-probe":
            raise PermissionError(errno.EACCES, "Permission denied")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", refuse)

    body = _client(tmp_path, Settings(data_dir=tmp_path)).get("/setup/privacy").text

    assert "Who writes the files" in body and "Voxtrama runs as" in body
    assert "Cannot write" in body
    assert "VOXTRAMA_RUN_AS_UID=4242\nVOXTRAMA_RUN_AS_GID=4343" in body
    assert f"chown -R {os.getuid()}:{os.getgid()} {tmp_path}" in body
    # Never advise opening the folder to everyone; the ?v=<mtime> of an
    # asset link can contain 777 by chance, so only the words are checked.
    assert "chmod 777" not in body and "777 " not in body


def test_a_writable_folder_shows_the_passed_test(tmp_path) -> None:
    body = _client(tmp_path, Settings(data_dir=tmp_path)).get("/setup/privacy").text

    assert "Write test passed" in body and "Cannot write" not in body
