"""GET and POST /profile: the one page where the local user writes their own name.

Until this route existed `User.given_name` was written in exactly one
place (the seed in migration 0011), so the name shown top right could
never be changed by the person it belongs to. This is the form that
closes that gap.

POST then redirect, never render-in-place: reloading a page that was
itself the result of a form submission re-submits it, and a browser
asking "confirm form resubmission" after saving a name is a question
nobody can answer well. 303 sends the browser to GET, where a refresh is
harmless (the taxonomy of a *request* failing is kept separate
from a *result* being unwelcome. This is neither: it is the ordinary
shape of a form that worked).

No authentication guards this, and that is deliberate rather than
an omission: the `local` profile has exactly one user and nothing to
authenticate as. Community Edition has nothing else on this page either:
the template says so in words, because two fields alone look like a
page that is missing something rather than one that is finished.

`setup=true` is the reuse of this exact form as the guided setup's
first step: same fields, same POST, same
NoLocalUserError tolerance. Only the surrounding chrome (the four-step
tracker) and where "Continue" sends the browser next differ. A second
route copying this logic would drift from it the first time either one
changed. A live "GP" preview as you type is left out: that
needs JavaScript this project does not use, so the circle here
shows the identity already on the User row, the same as every reload.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.settings import Settings
from voxtrama.db.people import NoLocalUserError, local_user
from voxtrama.edition import current_policy
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    read_identity,
    sidebar_items,
    stored_theme,
    theme_choices,
)

router = APIRouter()

PROFILE_PATH = "/profile"
SETUP_NEXT_PATH = "/setup/local-processing"


def _render(
    session: DbDep, translator: TranslatorDep, saved: bool, setup: bool, settings: Settings
) -> HTMLResponse:
    identity = read_identity(session)
    template = templates_environment.get_template("pages/profile.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=sidebar_items("profile"),
                identity=identity,
                saved=saved,
                setup=setup,
                wizard_steps=None,
                theme_choices=theme_choices(stored_theme(session)),
                origin=PROFILE_PATH,
                breadcrumb=None,
            )
        )
    )


@router.get(PROFILE_PATH, response_class=HTMLResponse)
def profile_page(
    session: DbDep,
    translator: TranslatorDep,
    settings: SettingsDep,
    saved: bool = False,
    setup: bool = False,
) -> Response:
    """The profile form, empty of nothing: a name never written shows blank fields.

    The name is no longer the guided setup's first step. An old
    `setup=true` link lands on the step that now opens it.
    """
    if setup:
        return RedirectResponse(SETUP_NEXT_PATH, status_code=status.HTTP_303_SEE_OTHER)
    return _render(session, translator, saved, setup, settings)


@router.post(PROFILE_PATH)
def save_profile(
    session: DbDep,
    given_name: Annotated[str, Form()] = "",
    family_name: Annotated[str, Form()] = "",
    setup: Annotated[bool, Form()] = False,
) -> RedirectResponse:
    """Store the name, then redirect to GET (or, mid-setup, to the next step).

    Both fields are stripped and stored as given: a family name is
    allowed to be empty: one-word names are ordinary, and migration
    0017 carries every existing installation in that shape. A
    **given** name that is empty is stored too rather than refused:
    clearing your own name is a legitimate thing to do, the identity
    circle then disappears (rendering.identity returns None), and the
    page says that is what happened instead of leaving a mystery. The
    field is therefore not `required` in the markup either. A browser
    refusing to submit would hide the same choice behind a tooltip. Mid
    setup a blank name is what "You can skip this and set later in
    Settings" promises, so it is honoured the same way: stored empty, no
    different code path.
    """
    destination = SETUP_NEXT_PATH if setup else f"{PROFILE_PATH}?saved=true"
    try:
        user = local_user(session)
    except NoLocalUserError:
        # A database nobody has migrated has no user to write to. Same
        # shape rendering.identity already tolerates for reading: no row
        # is the normal state of a fresh schema, not a fault to raise on.
        return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    # Only the fields the edition's policy allows are written.
    policy = current_policy()
    if policy.allows_profile_field("given_name"):
        user.given_name = given_name.strip()
    if policy.allows_profile_field("family_name"):
        user.family_name = family_name.strip()
    session.commit()
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
