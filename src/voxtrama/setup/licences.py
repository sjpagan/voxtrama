"""What a model's licence text has to yield: an SPDX identifier when it
is unambiguous, never a guess, and the permissive/not-permissive call that
decides both the asterisk and the proposed model.

Pure text classification (no network, no I/O), so this lives under
setup/ next to context_cap.py and not under providers/: both are a
business rule applied to a fact providers.ollama_show already read, not
a way of reading one. No "family -> licence" table stands in for the
text itself: a model this project has never heard of comes back
unrecognised, and unrecognised takes the asterisk like a licence known to
be restrictive.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.providers.probe import ProviderModel

# The permissive licences, as a constant instead of a condition spread through
# the code: MIT, Apache-2.0, BSD-2-Clause and BSD-3-Clause, nothing else.
# The others are usable, but for a summary a permissive model does the
# same job, so preferring one costs no function.
PERMISSIVE = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"})


# How much text is searched for a permissive identifier. A licence declares
# itself at the top: MIT in the first line, Apache in the first two. Further
# down a licence file, those names appear for another reason: third-party
# notices citing the licences of included components.
_OPENING_CHARS = 400

# Searched first and across the **whole** text, not only the opening: if a
# document names the Gemma Terms or the Llama licence anywhere, it is not
# MIT, whatever else it cites further down.
_RESTRICTIVE = (
    (("GEMMA TERMS OF USE",), "Gemma Terms of Use"),
    (("LLAMA", "COMMUNITY LICENSE"), "Llama Community License"),
)

_PERMISSIVE_MARKERS = (
    (("APACHE LICENSE", "VERSION 2.0"), "Apache-2.0"),
    (("MIT LICENSE",), "MIT"),
    (("BSD 3-CLAUSE",), "BSD-3-Clause"),
    (("BSD 2-CLAUSE",), "BSD-2-Clause"),
)


def recognise_licence(text: str | None) -> str | None:
    """The identifier `text` declares, or None when it cannot be read
    without ambiguity. A wrong recognition is a false statement about a
    right, so an unmatched text stays unrecognised
    instead of borrowing the closest-looking identifier.

    The order is the safety property. Restrictive markers are tested
    first and against the whole document, permissive ones only against
    its opening. Reversed, a restrictive licence whose third-party
    notices mention "the MIT License" would come back permissive, and a
    false permissive is the one error this module must not make: it
    drops the asterisk and can leave that model preselected. An
    unrecognised text costs a reader one click. A wrongly permissive one
    costs them the warning entirely.
    """
    if not text:
        return None
    upper = text.upper()
    for markers, sigla in _RESTRICTIVE:
        if all(marker in upper for marker in markers):
            return sigla
    opening = upper[:_OPENING_CHARS]
    for markers, sigla in _PERMISSIVE_MARKERS:
        if all(marker in opening for marker in markers):
            return sigla
    return None


@dataclass(frozen=True)
class ModelLicence:
    """One model's licence, classified from a single ModelFacts reading:
    the identifier if recognised, whether it counts as permissive, and the
    text exactly as the model declared it, for the asterisk's disclosure.
    """

    spdx: str | None
    permissive: bool
    text: str | None


def classify_licence(facts: ModelFacts) -> ModelLicence:
    """`facts.licence_text` turned into what the row and the asterisk need."""
    spdx = recognise_licence(facts.licence_text)
    return ModelLicence(spdx=spdx, permissive=spdx in PERMISSIVE, text=facts.licence_text)


def first_permissive_model(
    models: tuple[ProviderModel, ...], licences_by_model: dict[str, ModelLicence]
) -> str | None:
    """The first installed model with a permissive licence, in Ollama's
    order (proposing means preselecting, never
    reordering). None when no installed model qualifies: a constrained
    model is then chosen deliberately, not found already picked.
    """
    for model in models:
        licence = licences_by_model.get(model.name)
        if licence is not None and licence.permissive:
            return model.name
    return None
