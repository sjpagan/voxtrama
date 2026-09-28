"""Internationalization: the gettext plumbing.

One rule everything else here leans on: the negotiated locale is a
property of a single HTTP request, never of the process. Two requests in
different languages must be servable by the same running process at the
same time, so nothing in this package is a module-level Translations
object or a call to gettext.install(). Both would be shared mutable
state, read by whichever request happens to run concurrently.

Translator (i18n.translator) is the request-scoped object everything else
hangs off: get_translator (i18n.dependency) builds one per FastAPI
request from the negotiated locale (i18n.negotiation) and its catalog
(i18n.catalogs), and i18n.jinja wires its gettext/ngettext into a single
template render without touching the shared Jinja Environment.
"""

from __future__ import annotations

from voxtrama.i18n.dependency import TranslatorDep, get_translator
from voxtrama.i18n.translator import Translator

__all__ = ["Translator", "TranslatorDep", "get_translator"]
