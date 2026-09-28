"""Executable checks for the file- and function-size thresholds of the architecture rules."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKED_ROOTS = [REPO_ROOT / "src", REPO_ROOT / "tests"]

MAX_FILE_LINES = 150
MAX_FUNCTION_LINES = 40


def checked_files() -> list[Path]:
    return sorted(p for root in CHECKED_ROOTS for p in root.rglob("*.py"))


def test_no_file_exceeds_line_limit():
    violations = [
        f"{path}: {count} lines"
        for path in checked_files()
        if (count := len(path.read_text().splitlines())) > MAX_FILE_LINES
    ]
    assert not violations, "\n".join(violations)


def function_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Line span of a function's body: first statement to last, inclusive.

    Deliberately excludes the `def` line, decorators and the signature:
    the rule is about the body.
    """
    first = node.body[0].lineno
    last = node.body[-1].end_lineno or node.body[-1].lineno
    return last - first + 1


def iter_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_no_function_exceeds_line_limit():
    violations = []
    for path in checked_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for func in iter_functions(tree):
            length = function_line_count(func)
            if length > MAX_FUNCTION_LINES:
                violations.append(f"{path}:{func.lineno}: '{func.name}' is {length} lines")
    assert not violations, "\n".join(violations)
