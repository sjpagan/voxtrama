# Translating Voxtrama

How it works: English is the source language, written
directly in the code and the templates, and every other language is a
GNU gettext catalog (`.po`/`.mo`) that replaces it. This page is the
practical guide to it: how to add a language, and how the
template that catalogs start from gets regenerated.

## Where catalogs live

| Location | Who puts things there |
|---|---|
| `src/voxtrama/locales/` | catalogs shipped with the package, committed to this repository |
| `$VOXTRAMA_DATA_DIR/locales/` | catalogs a user adds to their own installation |

Both are read at startup, for every locale Voxtrama finds a compiled
`.mo` for. If a locale exists in both places, the one in
`$VOXTRAMA_DATA_DIR/locales/` wins: it is the user's own choice, not
ours to override.

**Adding a language never requires rebuilding the package.** Compile a
catalog and drop it into `$VOXTRAMA_DATA_DIR/locales/<locale>/LC_MESSAGES/messages.mo`,
then restart Voxtrama.

## Adding a language

1. Install Babel in your environment: `pip install babel` (it is already
   a runtime dependency of Voxtrama itself).
2. Initialize a catalog for your locale from the template:

   ```sh
   pybabel init -i src/voxtrama/locales/messages.pot \
       -d src/voxtrama/locales -l <locale>
   ```

   This creates `src/voxtrama/locales/<locale>/LC_MESSAGES/messages.po`,
   with the plural-forms rule for `<locale>` already filled in from CLDR.
   Do not hand-edit that header.
3. Fill in the `msgstr` for every entry in that `.po` file.
4. Compile it to the `.mo` file gettext actually reads:

   ```sh
   pybabel compile -d src/voxtrama/locales -l <locale>
   ```
5. If you are contributing the language back to the project, commit both
   the `.po` and the `.mo` file under `src/voxtrama/locales/<locale>/`.
   If you are translating for your own installation only, copy that same
   `LC_MESSAGES/messages.mo` file into
   `$VOXTRAMA_DATA_DIR/locales/<locale>/LC_MESSAGES/` instead: nothing
   under `src/` needs to change.

A missing string in an otherwise-complete catalog is not an error: it
shows in English, never as a raw key.

## Regenerating the template

`src/voxtrama/locales/messages.pot` is a generated file, committed on the
same terms as the built CSS (see the SCSS build): it is what a translator
starts from, so it has to be in the repository even though nothing reads
it at runtime.

Regenerate it after adding or changing translatable strings:

```sh
pybabel extract -F babel.cfg --project=voxtrama --version=0.1.0 \
    -o src/voxtrama/locales/messages.pot .
```

`babel.cfg` at the repository root tells the extractor to scan every
Python module under `src/voxtrama/` and every Jinja template under
`src/voxtrama/web/templates/`.

Once the template has new or changed entries, bring existing catalogs up
to date with:

```sh
pybabel update -i src/voxtrama/locales/messages.pot -d src/voxtrama/locales
```

## What is never translated

Log messages, the stable `code` field of an error, workflow/skill/schema
identifiers, and content produced by a model (a transcript, a summary)
are not part of the interface's i18n and must not be wrapped in a
translation call.

## Marking a string for translation

In Python:

```python
from voxtrama.i18n import Translator

message = translator.gettext("Recording deleted")
```

In a Jinja template:

```jinja
<p>{{ _("Recording deleted") }}</p>
{% trans count=recordings|length %}
  {{ count }} recording
{% pluralize %}
  {{ count }} recordings
{% endtrans %}
```

Both read from the `Translator` negotiated for the current request. See
`src/voxtrama/i18n/` for how that negotiation and the Jinja wiring work.
