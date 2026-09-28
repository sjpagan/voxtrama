"""Tests for voxtrama.humanize: numbers formatted the way a person reads them."""

from __future__ import annotations

from voxtrama.humanize import human_bytes


def test_bytes_are_printed_the_way_a_person_reads_them():
    assert human_bytes(512) == "512 B"
    assert human_bytes(484 * 1024 * 1024) == "484 MB"
    assert human_bytes(1536 * 1024 * 1024) == "1.5 GB"
