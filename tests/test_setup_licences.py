"""setup.licences: recognising a sigla from raw text, and the permissive
set applied to it: pure classification, no network.
"""

from __future__ import annotations

from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.providers.probe import ProviderModel
from voxtrama.setup.licences import (
    ModelLicence,
    classify_licence,
    first_permissive_model,
    recognise_licence,
)


def test_apache_license_version_2_is_recognised() -> None:
    text = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/"

    assert recognise_licence(text) == "Apache-2.0"


def test_mit_license_is_recognised() -> None:
    assert recognise_licence("MIT License\n\nCopyright (c) ...") == "MIT"


def test_bsd_3_clause_is_recognised() -> None:
    assert recognise_licence("BSD 3-Clause License") == "BSD-3-Clause"


def test_bsd_2_clause_is_recognised() -> None:
    assert recognise_licence("BSD 2-Clause License") == "BSD-2-Clause"


def test_gemma_terms_of_use_is_recognised() -> None:
    text = "Gemma Terms of Use\nLast modified: February 21, 2024\nBy using, reproducing..."

    assert recognise_licence(text) == "Gemma Terms of Use"


def test_llama_community_license_is_recognised_case_insensitively() -> None:
    text = "llama 3 community license agreement"

    assert recognise_licence(text) == "Llama Community License"


def test_an_unrecognisable_text_returns_none_not_a_guess() -> None:
    """The case that decides the rule: no sigla looks
    close enough to stand in for one nobody wrote down for us."""
    text = "Ozelot Public Licence 3.1, free for non-commercial tinkering"

    assert recognise_licence(text) is None


def test_missing_text_returns_none() -> None:
    assert recognise_licence(None) is None


_TEXT_FOR = {
    "MIT": "MIT License",
    "Apache-2.0": "Apache License\nVersion 2.0",
    "BSD-2-Clause": "BSD 2-Clause License",
    "BSD-3-Clause": "BSD 3-Clause License",
}


def test_the_permissive_four_are_permissive() -> None:
    for spdx, text in _TEXT_FOR.items():
        facts = ModelFacts(context_length=None, licence_text=text)
        assert classify_licence(facts).permissive is True, spdx


def test_gemma_is_recognised_but_not_permissive() -> None:
    facts = ModelFacts(context_length=None, licence_text="Gemma Terms of Use")

    licence = classify_licence(facts)

    assert licence.spdx == "Gemma Terms of Use"
    assert licence.permissive is False


def test_unrecognised_text_is_not_permissive_either() -> None:
    facts = ModelFacts(context_length=None, licence_text="Something nobody has seen before")

    licence = classify_licence(facts)

    assert licence.spdx is None
    assert licence.permissive is False
    assert licence.text == "Something nobody has seen before"


def test_first_permissive_model_skips_the_constrained_first_one() -> None:
    models = (
        ProviderModel(name="model-a", size_bytes=None),
        ProviderModel(name="model-b", size_bytes=None),
    )
    licences = {
        "model-a": ModelLicence(spdx="Gemma Terms of Use", permissive=False, text="..."),
        "model-b": ModelLicence(spdx="Apache-2.0", permissive=True, text="..."),
    }

    assert first_permissive_model(models, licences) == "model-b"


def test_first_permissive_model_returns_none_when_all_are_constrained() -> None:
    models = (
        ProviderModel(name="model-a", size_bytes=None),
        ProviderModel(name="model-b", size_bytes=None),
    )
    licences = {
        "model-a": ModelLicence(spdx="Gemma Terms of Use", permissive=False, text="..."),
        "model-b": ModelLicence(spdx=None, permissive=False, text=None),
    }

    assert first_permissive_model(models, licences) is None


def test_first_permissive_model_never_reorders_the_list() -> None:
    """Proposing means preselecting, not moving rows.
    Asserted here by picking the *second* permissive model over the first,
    both permissive, to show the order asked for is the order returned."""
    models = (
        ProviderModel(name="model-a", size_bytes=None),
        ProviderModel(name="model-b", size_bytes=None),
    )
    licences = {
        "model-a": ModelLicence(spdx="MIT", permissive=True, text="..."),
        "model-b": ModelLicence(spdx="Apache-2.0", permissive=True, text="..."),
    }

    assert first_permissive_model(models, licences) == "model-a"
