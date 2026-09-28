"""`voxtrama compare`, through the CLI: exit codes and path handling.

The comparison logic itself is test_manifest_comparison.py's job. This only
proves the command finds its input and turns report.compare()'s exit code
into the process's own, the same split cli/commands/compare.py keeps.
"""

from __future__ import annotations

import json
from pathlib import Path

from fakes.manifest import manifest_dict
from typer.testing import CliRunner

from voxtrama.cli.main import app

runner = CliRunner()


def _write(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest))


def test_identical_manifests_exit_zero(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, manifest_dict())
    _write(b, manifest_dict())

    result = runner.invoke(app, ["compare", str(a), str(b)])

    assert result.exit_code == 0
    assert "No differences that count." in result.output


def test_a_counted_difference_exits_one(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    manifest = manifest_dict()
    _write(a, manifest)
    manifest["environment"]["hardware_profile_used"] = "high"
    _write(b, manifest)

    result = runner.invoke(app, ["compare", str(a), str(b)])

    assert result.exit_code == 1
    assert "hardware_profile_used" in result.output


def test_a_run_folder_is_accepted_in_place_of_the_file(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    _write(run_dir / "manifest.json", manifest_dict())
    other = tmp_path / "b.json"
    _write(other, manifest_dict())

    result = runner.invoke(app, ["compare", str(run_dir), str(other)])

    assert result.exit_code == 0


def test_a_missing_file_exits_two(tmp_path: Path):
    a = tmp_path / "a.json"
    _write(a, manifest_dict())
    missing = tmp_path / "missing.json"

    result = runner.invoke(app, ["compare", str(a), str(missing)])

    assert result.exit_code == 2
