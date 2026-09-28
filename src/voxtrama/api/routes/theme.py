"""POST /theme: store the chosen theme and return to the page it was chosen from.

No GET here: there is no theme page. The control lives in the header of
every page, so this route's only job is to write the choice and send the
browser back where it was.

**Back where it was**, not to the home page: a control present on every
page that moves you somewhere else each time you use it is worse than no
control. The origin comes from a hidden field the form itself renders,
not from `Referer`, which a browser may withhold. It is checked to
be a path on this site before being used, because an open redirect is
what this pattern turns into when the value is trusted (`//evil.example`
is a valid URL, not a path on this app).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep
from voxtrama.db.people import NoLocalUserError, local_user
from voxtrama.rendering.theme import DEFAULT_THEME, Theme

router = APIRouter()


def _safe_origin(raw: str) -> str:
    """`raw` if it is a path on this site, "/" otherwise.

    A path starting with two slashes is a protocol-relative URL to
    another host (the case that turns "go back where you were" into an
    open redirect), so it is rejected along with anything that does not
    start with a slash at all.
    """
    return raw if raw.startswith("/") and not raw.startswith("//") else "/"


@router.post("/theme")
def choose_theme(
    session: DbDep,
    theme: Annotated[str, Form()] = DEFAULT_THEME.value,
    origin: Annotated[str, Form()] = "/",
) -> RedirectResponse:
    """Store the choice, then redirect to GET so a refresh does not resubmit it.

    An unknown value stores the default rather than 422: the form only
    ever submits one of three, so a fourth means a hand-made request, and
    falling back to "follow the system" is a harmless answer to one.
    """
    try:
        user = local_user(session)
    except NoLocalUserError:
        # No user row to write to: the shape of a database built straight
        # from the models, which rendering.theme already tolerates by
        # reading the default.
        return RedirectResponse(_safe_origin(origin), status_code=status.HTTP_303_SEE_OTHER)
    try:
        chosen = Theme(theme)
    except ValueError:
        chosen = DEFAULT_THEME
    user.theme = chosen.value
    session.commit()
    return RedirectResponse(_safe_origin(origin), status_code=status.HTTP_303_SEE_OTHER)
