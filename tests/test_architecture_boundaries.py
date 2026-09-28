"""Executable checks for the process- and distribution-boundary rules.

queue/base.py must not import rq or redis (it is the interface
the desktop target has to be able to satisfy without either). No tracked
file may be a media asset outside tests/fixtures/ (no media file
may be tracked at all, for licensing reasons). No module under src/ may
call print() (every log line goes through our own formatter,
which is the only way the field allow-list and the PII exclusions hold).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "voxtrama"

MEDIA_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".opus",
    ".flac",
    ".ogg",
    ".mp4",
    ".mkv",
    ".mov",
    ".rttm",
}
FIXTURES_PREFIX = "tests/fixtures/"


def test_queue_base_does_not_import_rq_or_redis():
    path = SRC_ROOT / "queue" / "base.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    banned = {"rq", "redis"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in banned:
                    violations.append(f"{path}:{node.lineno}: imports '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in banned:
                violations.append(f"{path}:{node.lineno}: imports from '{node.module}'")
    assert not violations, "\n".join(violations)


def tracked_files() -> list[str]:
    """Tracked file paths, via git if present, else an equivalent scan.

    git is not installed in python:3.11-slim. A checkout in CI contains
    exactly the tracked files, so scanning the filesystem there gives the
    same answer as `git ls-files` would. This must never silently skip.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0:
        return result.stdout.splitlines()
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    return [
        str(p.relative_to(REPO_ROOT))
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and not skip_dirs & set(p.relative_to(REPO_ROOT).parts)
    ]


def test_no_tracked_media_files():
    violations = [
        f
        for f in tracked_files()
        if Path(f).suffix.lower() in MEDIA_EXTENSIONS and not f.startswith(FIXTURES_PREFIX)
    ]
    assert not violations, f"tracked media files outside tests/fixtures/: {violations}"


def test_no_print_calls_under_src():
    violations = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    violations.append(f"{path}:{node.lineno}: print() call")
    assert not violations, "\n".join(violations)
