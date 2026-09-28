"""Loading catalogs from the package and from $VOXTRAMA_DATA_DIR."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.catalog import write_catalog

from voxtrama.i18n import catalogs

_ITALIAN_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"

msgid "Hello"
msgstr "Ciao"
"""

_ITALIAN_OVERRIDE_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"

msgid "Hello"
msgstr "Salve"
"""


@pytest.fixture
def package_locales(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the "packaged" catalogs at an empty, disposable directory."""
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", package_dir)
    return package_dir


def test_a_locale_with_no_catalog_anywhere_is_null_translations(package_locales: Path) -> None:
    translations = catalogs.load_translations("it", data_dir=None)
    assert translations.gettext("Hello") == "Hello"


def test_the_packaged_catalog_is_read_when_there_is_no_external_one(
    package_locales: Path, tmp_path: Path
) -> None:
    write_catalog(package_locales, "it", _ITALIAN_PO)

    translations = catalogs.load_translations("it", data_dir=tmp_path / "data")

    assert translations.gettext("Hello") == "Ciao"


def test_an_external_catalog_is_read_without_a_packaged_one(
    package_locales: Path, tmp_path: Path
) -> None:
    data_dir = tmp_path / "data"
    write_catalog(data_dir / "locales", "it", _ITALIAN_PO)

    translations = catalogs.load_translations("it", data_dir=data_dir)

    assert translations.gettext("Hello") == "Ciao"


def test_the_external_catalog_wins_over_the_packaged_one(
    package_locales: Path, tmp_path: Path
) -> None:
    """Same locale in both places, the user's own installation wins."""
    write_catalog(package_locales, "it", _ITALIAN_PO)
    data_dir = tmp_path / "data"
    write_catalog(data_dir / "locales", "it", _ITALIAN_OVERRIDE_PO)

    translations = catalogs.load_translations("it", data_dir=data_dir)

    assert translations.gettext("Hello") == "Salve"


def test_available_locales_always_includes_english(package_locales: Path) -> None:
    assert "en" in catalogs.available_locales(data_dir=None)


def test_available_locales_reports_both_packaged_and_external(
    package_locales: Path, tmp_path: Path
) -> None:
    write_catalog(package_locales, "it", _ITALIAN_PO)
    data_dir = tmp_path / "data"
    write_catalog(data_dir / "locales", "fr", _ITALIAN_PO)

    assert catalogs.available_locales(data_dir) == {"en", "it", "fr"}


def test_an_external_catalog_is_picked_up_without_rebuilding_the_package(
    package_locales: Path, tmp_path: Path
) -> None:
    """An external catalog appears without
    touching anything under the package: adding the file is enough."""
    data_dir = tmp_path / "data"
    assert catalogs.load_translations("it", data_dir).gettext("Hello") == "Hello"

    write_catalog(data_dir / "locales", "it", _ITALIAN_PO)

    assert catalogs.load_translations("it", data_dir).gettext("Hello") == "Ciao"
