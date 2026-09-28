"""A version query string for every file under web/static.

`voxtrama.min.css` (and the three JS files under static/js) are served
under the same URL from one build to the next, and a browser that has
ever fetched one keeps it until told otherwise. That turned "the CSS
rules are already in the file" into "the page looks unstyled" four
times in one day.

The fix (`?v=<mtime>`): every static file gets a version from its
last-modified time, read once when this module is imported (per request
would cost a stat() call on every page), and appended as `?v=` on the
URL a template asks for. A rebuilt file gets a new mtime and a new URL,
so no cached copy of the old one is reused.
"""

from __future__ import annotations

from pathlib import Path

# Mirrors how api.app.STATIC_DIR is derived (same sibling directory,
# computed independently like TEMPLATES_DIR and PACKAGE_LOCALES_DIR
# elsewhere) instead of importing api.app, which would pull the whole
# FastAPI app into this module for one Path.
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


def _asset_versions(directory: Path) -> dict[str, str]:
    """One mtime-derived version per file under `directory`, read once."""
    versions: dict[str, str] = {}
    if not directory.is_dir():
        return versions
    for file in directory.rglob("*"):
        if file.is_file():
            relative = file.relative_to(directory).as_posix()
            versions[relative] = str(int(file.stat().st_mtime))
    return versions


_ASSET_VERSIONS = _asset_versions(STATIC_DIR)


def static_url(path: str) -> str:
    """`/static/<path>`, with `?v=<mtime>` when `path` is a real static file.

    A path not found at import time (a typo, or a file added after
    startup) gets no suffix. It resolves to a plain `/static/<path>` and
    fails as an ordinary 404 instead of one hidden behind a stale version.
    """
    version = _ASSET_VERSIONS.get(path)
    suffix = f"?v={version}" if version else ""
    return f"/static/{path}{suffix}"
