"""How many custom workflows the edition allows, enforced on the server.

A custom workflow is one that exists only in the data directory: a user's
copy that covers a shipped workflow of the same name is an edit of that
workflow, not a new one, and does not count. The limit comes from
edition.current_policy() and is read by three callers (the list of
workflows, the lookup of one by name, and the write of a new one), so a
workflow beyond the limit is neither shown, nor run, nor created.

When there are more custom workflows on disk than the policy allows (files
copied in by hand), the first ones in alphabetical order are kept: the
same answer every time, whatever order the filesystem lists them in.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.edition import PolicyLimitError, current_policy
from voxtrama.workflow.document import document_roots

_FOLDER = "workflows"


def _names(root: Path) -> set[str]:
    try:
        return {path.stem for path in root.glob("*.yaml")}
    except OSError:
        return set()


def custom_workflow_names() -> list[str]:
    """Every workflow that lives only in the data directory, alphabetically."""
    user_root, *system_roots = document_roots(_FOLDER)
    shipped = set().union(*(_names(root) for root in system_roots))
    return sorted(_names(user_root) - shipped)


def refused_custom_workflows() -> set[str]:
    """The custom workflows beyond what the edition allows."""
    return set(custom_workflow_names()[current_policy().custom_workflows :])


def ensure_room_for(name: str) -> None:
    """Raise PolicyLimitError when writing `name` would add one custom workflow too many."""
    user_root, *system_roots = document_roots(_FOLDER)
    if any(name in _names(root) for root in (user_root, *system_roots)):
        return
    if len(custom_workflow_names()) >= current_policy().custom_workflows:
        raise PolicyLimitError(
            f"The Community Edition allows {current_policy().custom_workflows} custom workflow(s)"
        )
