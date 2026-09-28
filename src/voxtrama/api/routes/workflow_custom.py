"""The custom workflow of the Workflows page: create, edit, delete.

GET /workflows/new is the form, empty («Start from scratch»), filled from
a system workflow (`?source=`, «Duplicate»), or filled from the custom one
being edited (`?edit=`). POST /workflows/custom writes it through
workflow.document_write.save_document, which enforces the edition's
limit, refused here first, with a sentence, rather than left to
surface as an error. POST /workflows/{name}/delete removes a custom one.
The system workflows are neither edited nor deleted.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import FormData

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.workflow_library import PATH
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.settings import get_settings
from voxtrama.edition import PolicyLimitError
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.catalog import list_workflow_names
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import sidebar_items, stored_theme, theme_choices
from voxtrama.rendering.skill_instructions import system_prompt
from voxtrama.rendering.workflow_custom import custom_form
from voxtrama.workflow.custom_build import build_custom_workflow
from voxtrama.workflow.custom_limit import custom_workflow_names
from voxtrama.workflow.document_write import save_document
from voxtrama.workflow.errors import WorkflowError
from voxtrama.workflow.instructions import InstructionsError, check_instructions
from voxtrama.workflow.loader import validate_workflow

router = APIRouter()


def _refuse(title: str, detail: str, code: str = "validation_failed") -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code=code, title=title, detail=detail
    )


def _custom_or_422(name: str) -> None:
    if name not in custom_workflow_names():
        raise _refuse("Only a custom workflow can change", f"'{name}' is a system workflow")


@router.get(f"{PATH}/new", response_class=HTMLResponse)
def custom_workflow_form(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    source: str | None = None,
    edit: str | None = None,
) -> HTMLResponse:
    """The form: empty, a copy of `source`, or the custom workflow `edit`."""
    if edit is not None:
        _custom_or_422(edit)
    named = edit or source
    workflow = load_workflow_or_422(named) if named else None
    form = custom_form(workflow, BUILTIN_SKILLS, editing=edit is not None)
    template = templates_environment.get_template("pages/workflow_custom.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=sidebar_items("workflows"),
                form=form,
                theme_choices=theme_choices(stored_theme(session)),
                origin=f"{PATH}/new",
            )
        )
    )


@router.post(f"{PATH}/custom")
async def save_custom_workflow(request: Request) -> RedirectResponse:
    """Write the custom workflow the form describes, then show it in the library."""
    form = await request.form()
    title = str(form.get("title") or "").strip()
    if not title:
        raise _refuse("A workflow needs a name", "title: empty")
    original = str(form.get("original") or "") or None
    if original is not None:
        _custom_or_422(original)
    source_name = str(form.get("source") or "") or original
    source = load_workflow_or_422(source_name) if source_name else None
    skills = dict(str(value).rpartition(":")[::2] for value in form.getlist("skill"))
    workflow = build_custom_workflow(
        title,
        str(form.get("description") or ""),
        skills,
        source,
        name=original,
        instructions=_instructions(form, skills),
    )
    if original is None and workflow.name in {*custom_workflow_names(), *_system_names()}:
        raise _refuse("That name is taken", f"a workflow called '{workflow.name}' exists already")
    try:
        validate_workflow(workflow, BUILTIN_SKILLS)
        save_document("workflows", workflow.name, workflow)
    except WorkflowError as exc:
        raise _refuse("The workflow is not valid", str(exc)) from exc
    except PolicyLimitError as exc:
        raise _refuse("No custom workflow left", str(exc), code="rule_rejected") from exc
    return RedirectResponse(f"{PATH}?workflow={workflow.name}", status.HTTP_303_SEE_OTHER)


def _instructions(form: FormData, skills: dict[str, str]) -> dict[str, str]:
    """The steps whose instructions differ from their skill's own."""
    edited = {}
    for name in skills:
        text = str(form.get(f"instructions:{name}") or "").replace("\r\n", "\n").strip()
        shipped = system_prompt(name)
        if not text or shipped is None or text == shipped.strip():
            continue
        try:
            check_instructions(text)
        except InstructionsError as exc:
            raise _refuse("These instructions cannot run", f"{name}: {exc}") from exc
        edited[name] = text + "\n"
    return edited


def _system_names() -> set[str]:
    return set(list_workflow_names()) - set(custom_workflow_names())


@router.post(PATH + "/{name}/delete")
def delete_custom_workflow(name: str) -> RedirectResponse:
    """Remove the custom workflow `name`; the jobs it ran keep their own copy."""
    _custom_or_422(name)
    (get_settings().data_dir / "workflows" / f"{name}.yaml").unlink(missing_ok=True)
    return RedirectResponse(PATH, status.HTTP_303_SEE_OTHER)
