"""Renders the page a browser lands on after a request failure: the HTML
counterpart to api.errors' own JSON body, for the request that asked for
one (api.error_accept.wants_html).

Kept apart from errors.py so that module stays under the file-size limit,
and so the JSON contract there never grows a template dependency: a
request that only ever sees a problem+json body should not make errors.py
import Jinja to serve it.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from voxtrama.api.templating import templates_environment
from voxtrama.config.settings import get_settings
from voxtrama.i18n.dependency import get_translator
from voxtrama.i18n.jinja import render_context


def render_error_page(
    request: Request, *, status_code: int, title: str, detail: str
) -> HTMLResponse:
    """The same failure `errors._problem_response` renders as JSON, as a page instead.

    No session read here, unlike api.templating.page_context: the page a
    person reaches by failing to complete an action is a dead end, not a
    place that needs the navbar's identity menu or sidebar. `title` and
    `detail` are the two fields the problem document already carries,
    passed straight through rather than reconstructed here.
    """
    translator = get_translator(request, get_settings())
    context = {"title": title, "detail": detail, **render_context(translator)}
    body = templates_environment.get_template("pages/error.html").render(**context)
    return HTMLResponse(content=body, status_code=status_code)
