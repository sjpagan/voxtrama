"""Wiring the translator into Jinja without a process-global catalog.

Jinja2 ships `Environment.install_gettext_translations()`, and it is the
wrong tool here: it stores the catalog on the shared Environment. That is
the concurrency bug the package docstring warns about: two requests in
different languages, served by the same process, would race over which
catalog is installed.

The extension itself is process-wide and stateless (it just teaches Jinja
the `{% trans %}` tag and the `_()` global), so install() adds it once,
when the Environment is built. Per-request translation runs each
`_() `/`{% trans %}` call back to whatever `gettext`/`ngettext` were passed
into *that* render (see render_context()), because Jinja resolves those
names from the template's own render context before it looks at the
Environment's globals.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, pass_context
from jinja2.runtime import Context
from markupsafe import Markup

from voxtrama.i18n.translator import Translator


def install(environment: Environment) -> None:
    """Add gettext support to `environment`. Call once, when it is built."""
    environment.add_extension("jinja2.ext.i18n")
    environment.newstyle_gettext = True


def render_context(translator: Translator) -> dict[str, object]:
    """Per-render variables a template needs for `{% trans %}` and `_()`.

    Merge this into every `template.render(...)` call alongside the
    template's own data. It makes that one render use
    `translator`'s locale instead of whatever the previous request used.
    `locale` rides along for the same reason: base.html's `<html lang>`
    must match what this render is translated into, not a fixed
    string that would be wrong as soon as negotiation picks anything but
    English.
    """
    return {
        "gettext": _markup_gettext(translator),
        "ngettext": _markup_ngettext(translator),
        "locale": translator.locale,
    }


# The translation is template source, written by us and by the translators,
# as trusted as the template around it: "Data &amp; privacy" is already
# HTML. With autoescape on (for security) it would be escaped a
# second time, so it is marked safe here, as Jinja's own newstyle gettext
# does. Values given to it are escaped by Markup's own `%`.


def _markup_gettext(translator: Translator):
    @pass_context
    def gettext(context: Context, message: str, **variables: Any) -> str:
        text = translator.gettext(message)
        if context.eval_ctx.autoescape:
            text = Markup(text)
        return text % variables if variables else text

    return gettext


def _markup_ngettext(translator: Translator):
    @pass_context
    def ngettext(context: Context, singular: str, plural: str, n: int, **variables: Any) -> str:
        text = translator.ngettext(singular, plural, n)
        if context.eval_ctx.autoescape:
            text = Markup(text)
        return text % variables if variables else text

    return ngettext
