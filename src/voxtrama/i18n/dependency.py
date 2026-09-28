"""FastAPI dependency that builds this request's Translator.

Follows api/deps.py's own shape: a plain function FastAPI calls per
request, exposed as an Annotated alias. Nothing here is cached with
lru_cache the way get_queue or get_engine are. Those are process-wide by
design. This returns a fresh Translator every call, because the locale it
carries belongs to one request, not to the process (see the package
docstring).

The explicit level of the locale resolution order (step 1, ahead of
Accept-Language) is carried by a `lang` query parameter: the 0.1 has no
language selector yet to write it anywhere sturdier, and a query parameter
is the one carrier that does not need one: a link like `/?lang=it`
already works.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from voxtrama.config.settings import Settings, get_settings
from voxtrama.i18n.catalogs import available_locales, load_translations
from voxtrama.i18n.negotiation import negotiate_locale
from voxtrama.i18n.translator import Translator


def get_translator(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Translator:
    """Negotiate this request's locale and load the catalog behind it."""
    locale = negotiate_locale(
        available=available_locales(settings.data_dir),
        explicit=request.query_params.get("lang"),
        accept_language=request.headers.get("accept-language"),
        default_locale=settings.default_locale,
    )
    return Translator(locale=locale, translations=load_translations(locale, settings.data_dir))


TranslatorDep = Annotated[Translator, Depends(get_translator)]
