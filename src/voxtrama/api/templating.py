"""The Jinja Environment that renders src/voxtrama/web/templates/.

Built once at import time, not per request: constructing an Environment
recompiles nothing by itself, but doing it per request would still mean
re-registering the i18n extension and re-reading the loader's search path
on every hit, work the process only has to do once. install() adds that
extension here because it is process-wide and stateless (see
voxtrama.i18n.jinja's docstring). The translator for one request is merged
into the render call itself, not stored on this Environment.

TEMPLATES_DIR is derived from this file's own location, the same way
i18n/catalogs.py locates PACKAGE_LOCALES_DIR, rather than through
jinja2.PackageLoader: voxtrama.web has no __init__.py (it holds templates,
scss and compiled static assets, not importable code), which makes it a
namespace package, and Path(__file__) resolves to the right place whether
voxtrama is running from this checkout or from an installed wheel.

`static_url` (rendering.assets) is registered as a global here rather than
merged into page_context()'s per-request dict: its own versions are read
once at import time, so every template calls it directly instead of every
route remembering to pass it along.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.health import read_health
from voxtrama.i18n.jinja import install, render_context
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.assets import static_url
from voxtrama.rendering.identity import header_full_name, header_initial
from voxtrama.rendering.theme import attribute, stored_theme
from voxtrama.setup.wizard_start import setup_pending
from voxtrama.workflow.output_languages import OUTPUT_LANGUAGES

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"

# Autoescape on, for security: transcript text, model output, job
# and speaker names are attacker-influenced, and every template printed them raw.
templates_environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
install(templates_environment)
templates_environment.globals["static_url"] = static_url
# The recap languages the job form offers, the same list everywhere.
templates_environment.globals["output_languages"] = OUTPUT_LANGUAGES


def page_context(
    session: Session, translator: Translator, *, settings: Settings | None = None, **extra: object
) -> dict[str, object]:
    """Everything every page needs, so no route has to remember it.

    `render_context` already carries the translator and its locale into a
    single render. The theme belongs in the same place for the same
    reason. Left to each route to pass, a page added later would render
    with no `data-theme` at all and silently ignore the person's choice,
    the kind of omission no test catches: the page renders, in the wrong colours.

    `theme_attribute` is None when the choice is "auto", and base.html
    omits the attribute entirely in that case: see rendering.theme on why
    an attribute spelling "auto" would break what auto is for.

    `user_initial` joins it here for the same reason: every page
    with a header needs it, it comes from `session` alone, and a route
    added later that forgot to pass it would silently show no identity
    circle rather than fail (the same kind of omission theme_attribute
    already guards against). `nav_items` stays out: which section is
    current is a route's own answer, not something session alone decides.

    `user_full_name` joins it for the same reason:
    the identity menu behind the circle needs the name written
    out in full, every page with a header opens that same menu, and it
    comes from `session` alone too. There is nothing here a route could
    know that this function does not already. profile.py separately
    passes its own `identity` (rendering.identity.Identity, the dataclass
    itself) as an *extra*, and that is a different thing: the profile
    *form* needs given_name and family_name apart to fill two input
    fields, which is a page-specific need this shared context has no
    business anticipating for every other page.
    `health` and `setup_pending` only when a route passes `settings`.
    """
    return {
        "theme_attribute": attribute(stored_theme(session)),
        "user_initial": header_initial(session),
        "user_full_name": header_full_name(session),
        "health": read_health(settings) if settings is not None else None,
        "setup_pending": settings is not None and setup_pending(settings.data_dir),
        **render_context(translator),
        **extra,
    }
