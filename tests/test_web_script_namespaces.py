"""Browser scripts do not clash over names.

The scripts in `static/js/` are classic files, not modules: they share a
single namespace, the global one. On 26 September 2026 `upload_dropzone.js`
declared `stringCatalog()` and `init()`, already declared by `runs_delete.js`.
On the home page the second one won, and the file box read the deletion's
string catalogue. No exception, no console line, and a green suite: the
defect only showed by looking at the page.

These tests read the files without running them. A declaration at the start
of a line (`function`, `const`, `let`, `var`, `class`) is at the file's top
level, so in the global namespace. Every script wraps itself in
`(function () { ... })();` and gives the others only what it exports on `window`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "src" / "voxtrama" / "web" / "static" / "js"

TOP_LEVEL_DECLARATION = re.compile(
    r"^(?:async\s+)?function\s*\*?\s*(\w+)|^(?:const|let|var|class)\s+(\w+)",
    re.MULTILINE,
)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _scripts() -> list[Path]:
    return sorted(JS_DIR.glob("*.js"))


def _top_level_names(path: Path) -> list[str]:
    source = BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8"))
    return [a or b for a, b in TOP_LEVEL_DECLARATION.findall(source)]


def test_the_scripts_directory_is_found():
    # Without this, a wrong path would let the other two tests pass on an
    # empty list.
    assert _scripts(), f"no script found in {JS_DIR}"


def test_no_script_declares_a_name_at_the_top_level():
    leaking = {p.name: names for p in _scripts() if (names := _top_level_names(p))}
    assert not leaking, (
        "these scripts declare names in the shared global namespace; wrap the "
        f"file in (function () {{ ... }})(); and export on window: {leaking}"
    )


def test_no_two_scripts_declare_the_same_top_level_name():
    declared_in: dict[str, list[str]] = defaultdict(list)
    for path in _scripts():
        for name in _top_level_names(path):
            declared_in[name].append(path.name)
    duplicated = {name: files for name, files in declared_in.items() if len(files) > 1}
    assert not duplicated, f"the same global name is declared by more than one script: {duplicated}"
