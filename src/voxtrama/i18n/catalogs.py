"""Loading gettext catalogs from the package and the user's data directory.

The catalogs shipped inside the package live in
`src/voxtrama/locales/`. A user who wants a language we do not ship drops
a compiled catalog into `$VOXTRAMA_DATA_DIR/locales/` and gets it without
rebuilding anything, which is the main reason for this design. When a locale
exists in both places, the external one wins: it is the user's own
installation, not ours to keep authority over.

English is never a catalog here: it is the source language, so
a missing translation already reads correctly by falling back to the
msgid itself (see Translator.gettext), and a missing catalog altogether
just means NullTranslations, which does the same thing.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from babel.support import NullTranslations, Translations

DOMAIN = "messages"
SOURCE_LOCALE = "en"
PACKAGE_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def _external_locales_dir(data_dir: Path | None) -> Path | None:
    return data_dir / "locales" if data_dir is not None else None


def _has_catalog(locale: str, locales_root: Path) -> bool:
    return (locales_root / locale / "LC_MESSAGES" / f"{DOMAIN}.mo").is_file()


@cache
def available_locales(data_dir: Path | None) -> frozenset[str]:
    """Locale codes with a compiled catalog, package or external, plus English.

    English needs no file on disk to be "available": it is the text
    already written in the templates and the code, not a translation of it.

    Cached for the life of the process, which is what docs/translating.md
    promises: a catalog dropped into the data directory is picked up on the
    next **restart**. Without the cache every request would scan the
    directory and reparse the catalog, and adding a language would silently
    work without a restart: nicer, but nobody decided it and the
    documentation would then be wrong about it. Tests that add a catalog
    under a path already read call `reset_catalog_cache()`.
    """
    locales = {SOURCE_LOCALE}
    for root in (PACKAGE_LOCALES_DIR, _external_locales_dir(data_dir)):
        if root is None or not root.is_dir():
            continue
        locales.update(entry.name for entry in root.iterdir() if _has_catalog(entry.name, root))
    return frozenset(locales)


@cache
def load_translations(locale: str, data_dir: Path | None) -> NullTranslations:
    """Load `locale`'s catalog, external overriding packaged.

    Returns plain NullTranslations when neither has one: its gettext()
    already returns the message unchanged, which is the fallback required
    for English and for any locale we merely negotiated into without ever
    having a catalog for it.

    Cached, and safe to share across requests in a way a Translator is
    not: a loaded catalog is read-only, while a Translator carries the
    locale one request negotiated.
    """
    external = _external_locales_dir(data_dir)
    if external is not None and _has_catalog(locale, external):
        return Translations.load(external, [locale], domain=DOMAIN)
    if _has_catalog(locale, PACKAGE_LOCALES_DIR):
        return Translations.load(PACKAGE_LOCALES_DIR, [locale], domain=DOMAIN)
    return NullTranslations()


def reset_catalog_cache() -> None:
    """Forget what is on disk. For tests that write a catalog mid-run.

    Not wired to anything at runtime: a restart is how a new language
    arrives (docs/translating.md), and an endpoint that reloaded catalogs
    would be a second way to do it that nobody asked for.
    """
    available_locales.cache_clear()
    load_translations.cache_clear()
