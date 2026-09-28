"""Builds a compiled gettext catalog on disk, for i18n tests.

Tests need a real `.mo` file to exercise babel.support.Translations
against: there is no fixture format simpler than the one gettext itself
reads. Writing the `.po` source and compiling it in-process (rather than
shelling out to `pybabel`) keeps a whole test catalog inline in the test
that needs it.
"""

from __future__ import annotations

import io
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from voxtrama.i18n.catalogs import reset_catalog_cache


def write_catalog(root: Path, locale: str, po_source: str) -> None:
    """Compile `po_source` and place it where `locale`'s catalog belongs.

    `root` is a locales directory, either the packaged one or an external
    `$VOXTRAMA_DATA_DIR/locales`: the layout below it is what
    i18n.catalogs expects either way.
    """
    catalog_dir = root / locale / "LC_MESSAGES"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog = read_po(io.StringIO(po_source), locale=locale, domain="messages")
    with (catalog_dir / "messages.mo").open("wb") as mo_file:
        write_mo(mo_file, catalog)
    # i18n.catalogs reads the disk once per process, because a language is
    # added by restarting (docs/translating.md). A test that writes a
    # catalog has just made that reading stale, and forgetting this here
    # would make every future i18n test depend on whether some earlier one
    # happened to touch the same directory first.
    reset_catalog_cache()
