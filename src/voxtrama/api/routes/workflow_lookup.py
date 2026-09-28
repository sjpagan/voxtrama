"""Resolve a workflow_name against the catalogue, the one way every route does it.

Not a route itself: the same relationship run_views.py has to run_create.py
and runs.py: several routes need this exact lookup (POST /runs and GET
/workflows/{name}/choices today, more to come), and each one
doing its own copy is how two routes quietly disagree about what "the
workflow does not exist" means. So it lives once, here, and every route
that takes a workflow_name imports it from here.
"""

from __future__ import annotations

from fastapi import status

from voxtrama.api.errors import ProblemException
from voxtrama.engine.catalog import WorkflowNotFoundError, load_named_workflow
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.errors import WorkflowError


def load_workflow_or_422(workflow_name: str) -> Workflow:
    """Resolve `workflow_name`, or raise the 422 a request failure gets here.

    422 is the closest taxonomy entry, not the accurate one: the
    request matches its schema, it is the name inside it that does not
    resolve. `rule_rejected` exists for a body a declared rule refuses,
    which is not this case: nothing refuses a workflow name, it simply is
    not in the catalogue. An unresolved reference is a third shape, still
    without its own entry, and the error taxonomy is closed and does not
    grow here.
    """
    try:
        return load_named_workflow(workflow_name)
    except (WorkflowNotFoundError, WorkflowError) as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_failed",
            title="The workflow could not be loaded",
            detail=str(exc),
        ) from exc
