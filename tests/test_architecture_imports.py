"""Executable check for the architecture's import-direction rule.

Split out of test_architecture.py (which keeps only the classification
check) so that adding rendering, the fourth layer, to the classification
data would not push that file past its own 150-line threshold.
"""

from __future__ import annotations

import ast

from _architecture import FORBIDDEN_FOR_CORE, classify, module_name, voxtrama_modules


def voxtrama_import_targets(tree: ast.AST) -> list[tuple[int, str]]:
    """(lineno, dotted target) for every `voxtrama.*` import in `tree`."""
    targets: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "voxtrama" or alias.name.startswith("voxtrama."):
                    targets.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] == "voxtrama":
                targets.append((node.lineno, node.module))
    return targets


def test_core_does_not_import_adapters_or_entrypoints():
    violations = []
    for path in voxtrama_modules():
        if classify(module_name(path)) != "core":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for lineno, target in voxtrama_import_targets(tree):
            imported = target.removeprefix("voxtrama").lstrip(".")
            layer = classify(imported) if imported else None
            if layer in FORBIDDEN_FOR_CORE:
                violations.append(f"{path}:{lineno}: core module imports {layer} target '{target}'")
    assert not violations, "\n".join(violations)
