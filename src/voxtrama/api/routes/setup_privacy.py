"""GET /setup/privacy: Settings › Data & privacy.

Where the data lives and how much room it takes, the model servers and
whether each is on this machine, what every workflow's steps do with the
content, the retention limit, whose card moved here from the
overview, and who writes the files with a real write per folder.
It only shows. The rules are applied elsewhere.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.diagnostics.write_access import write_access
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import sidebar_items, stored_theme, theme_choices
from voxtrama.rendering.data_privacy import privacy_view
from voxtrama.setup.installation import read_installation_config

router = APIRouter()

PATH = "/setup/privacy"


@router.get(PATH, response_class=HTMLResponse)
def privacy_page(session: DbDep, settings: SettingsDep, translator: TranslatorDep) -> HTMLResponse:
    """The page, read now: nothing here is cached or computed ahead."""
    template = templates_environment.get_template("pages/setup_privacy.html")
    page = page_context(
        session,
        translator,
        settings=settings,
        nav_items=sidebar_items("setup-privacy"),
        theme_choices=theme_choices(stored_theme(session)),
        origin=PATH,
        view=privacy_view(settings),
        access=write_access(settings.data_dir, settings.models_dir),
        config=read_installation_config(settings.data_dir),
    )
    return HTMLResponse(template.render(**page))
