"""Tests for providers.version: numeric comparison, never lexicographic.

This trap is the reason this file exists: "0.34.2" >= "0.9.0" is False as
a string compare ("3" < "9"), and True as what the numbers mean. Written
first, to watch it fail against a naive implementation before it passes
against this one.
"""

from __future__ import annotations

import pytest

from voxtrama.providers.version import meets_minimum, parse_version


def test_a_higher_minor_version_meets_a_lower_minimum_even_when_longer_as_a_string() -> None:
    """The trap: 0.34.2 is newer than 0.9.0 by 25 minor releases, not older."""
    assert meets_minimum("0.34.2", "0.9.0") is True


@pytest.mark.parametrize("unparseable", ["dev", "", "  ", "1.2.dev0"])
def test_a_version_that_does_not_decompose_is_unknown_not_a_failure(unparseable: str) -> None:
    assert parse_version(unparseable) is None
    assert meets_minimum(unparseable, "0.9.0") is None


def test_a_missing_version_is_unknown_not_a_failure() -> None:
    assert meets_minimum(None, "0.9.0") is None


def test_an_equal_version_meets_the_minimum() -> None:
    assert meets_minimum("0.9.0", "0.9.0") is True


def test_a_lower_version_does_not_meet_the_minimum() -> None:
    assert meets_minimum("0.8.9", "0.9.0") is False
