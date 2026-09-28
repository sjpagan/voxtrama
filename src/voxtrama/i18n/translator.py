"""The per-request translation handle.

One Translator per request, pairing the locale that request negotiated
with the catalog behind it. It is created fresh by i18n.dependency for
every request and held nowhere else. The package docstring explains why a
shared instance would be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from gettext import NullTranslations


@dataclass(frozen=True)
class Translator:
    """The negotiated locale plus the gettext calls that read from its catalog."""

    locale: str
    translations: NullTranslations

    def gettext(self, message: str) -> str:
        """Translate `message`, or return it unchanged if the catalog lacks it.

        That fallback is not something this method implements: it is what
        gettext already does when a msgid is missing, which is right here
        because `message` is itself the English source text,
        not an opaque key.
        """
        return self.translations.gettext(message)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """Translate a plural form, using the catalog's own CLDR plural rule."""
        return self.translations.ngettext(singular, plural, n)
