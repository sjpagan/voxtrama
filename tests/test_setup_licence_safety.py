"""The direction of the error setup.licences must never make.

Recognising a licence wrongly is a false statement about a right, and the
two directions are not symmetric. An unrecognised text costs a reader one
click: it still takes the asterisk. A text wrongly read as permissive
costs them the warning altogether: the asterisk disappears and that model
can be left preselected.

So the order inside recognise_licence is a safety property, and these
are the cases that hold it in place. They are split from
test_setup_licences.py (which covers what the module does) because what
it must never do is a subject of its own, and because the project caps a file
at 150 lines.
"""

from __future__ import annotations

from voxtrama.setup.licences import PERMISSIVE, recognise_licence


def test_a_restrictive_licence_that_mentions_mit_is_not_read_as_permissive() -> None:
    """The one error this module must not make.

    A licence file that carries third-party notices names other licences
    inside itself; matching "MIT License" anywhere in the document would
    turn a restricted model permissive, drop its asterisk and let it be
    preselected. Restrictive markers are therefore tested first, and
    against the whole text.
    """
    text = (
        "Gemma Terms of Use\n"
        "Last modified: February 21, 2024\n\n"
        "By using Gemma you agree to be bound by this Agreement.\n\n"
        "THIRD-PARTY NOTICES\n"
        "Portions of this software are distributed under the MIT License.\n"
    )

    assert recognise_licence(text) == "Gemma Terms of Use"
    assert recognise_licence(text) not in PERMISSIVE


def test_a_permissive_sigla_named_only_deep_in_the_text_is_not_recognised() -> None:
    """A licence declares itself in its opening lines. A name appearing
    far below is a citation, not a declaration. An unrecognised text
    still takes the asterisk, so refusing to read it is the safe answer.
    """
    text = "Some Vendor Model Licence\n\n" + ("filler clause. " * 80) + "\nMIT License\n"

    assert recognise_licence(text) is None
