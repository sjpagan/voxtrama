"""What gets counted while weights download, and what must not.

Every case here was taken from watching `snapshot_download` run for real, not
from reading its signature: the ones it builds, in which order, and with which
arguments, are not things the documentation says.
"""

from __future__ import annotations

from voxtrama.weights.reporting import reporting_tqdm


def _bar(tqdm_class, **kwargs):
    """Build one bar the way huggingface_hub builds them, without drawing it."""
    return tqdm_class(disable=True, **kwargs)


def test_a_bar_that_counts_files_is_not_added_to_the_bytes():
    """The first defect: "10 MB of 4 B (258259375%)".

    huggingface_hub builds a counter for files as well ("Fetching 4 files"),
    and adding that 4 into a total of bytes produced a percentage in the
    hundreds of millions.
    """
    seen = []
    tqdm_class = reporting_tqdm(lambda done, total: seen.append((done, total)))

    files = _bar(tqdm_class, total=4, unit="it")
    payload = _bar(tqdm_class, total=484 * 1024 * 1024, unit="B")
    files.update(1)
    payload.update(1024)

    assert seen == [(1024, 484 * 1024 * 1024)]


def test_a_total_that_arrives_late_is_still_reported():
    """The second defect: no denominator at all in a real run.

    The byte counters are built with `total=0` and told their real total
    afterwards: their description literally starts as "Reconstructing
    (incomplete total...)". Reading the total in the constructor reads that
    zero and the caller never gets a denominator.
    """
    seen = []
    tqdm_class = reporting_tqdm(lambda done, total: seen.append((done, total)))

    bar = _bar(tqdm_class, total=0, initial=0, unit="B")
    bar.update(1024)
    bar.total = 484 * 1024 * 1024  # what huggingface_hub does once it knows
    bar.update(1024)

    assert seen[-1] == (2048, 484 * 1024 * 1024)


def test_the_nominal_size_stands_in_until_the_real_total_is_known():
    """A figure with an approximate denominator beats a figure with none."""
    seen = []
    tqdm_class = reporting_tqdm(
        lambda done, total: seen.append((done, total)), fallback_total=567 * 1024 * 1024
    )

    _bar(tqdm_class, total=0, unit="B").update(4096)

    assert seen == [(4096, 567 * 1024 * 1024)]


def test_the_same_bytes_counted_twice_are_reported_once():
    """`snapshot_download` builds two byte counters: network, and disk.

    They describe the same download. Summing them reports twice the bytes
    that are moving.
    """
    seen = []
    tqdm_class = reporting_tqdm(lambda done, total: seen.append(done))

    transfer = _bar(tqdm_class, total=100, unit="B", desc="Downloading bytes")
    reconstruct = _bar(tqdm_class, total=100, unit="B", desc="Reconstructing")
    transfer.update(40)
    reconstruct.update(40)
    transfer.update(10)

    assert seen == [40, 50]


def test_bytes_are_counted_even_when_the_bar_is_disabled():
    """tqdm leaves its own counter alone when disabled, and HF disables freely.

    Reading `self.n` looked tidier and reported zero for every download whose
    bar had been turned off, which is most of them in a container.
    """
    seen = []
    tqdm_class = reporting_tqdm(lambda done, total: seen.append(done))

    bar = _bar(tqdm_class, total=100, unit="B")
    bar.update(40)

    assert bar.n == 0  # tqdm itself counted nothing
    assert seen == [40]  # and the caller was told the truth anyway


def test_two_downloads_do_not_share_a_counter():
    """Counters live per call, so a second download does not resume the first."""
    first_seen, second_seen = [], []
    first = reporting_tqdm(lambda done, total: first_seen.append(done))
    second = reporting_tqdm(lambda done, total: second_seen.append(done))

    _bar(first, total=100, unit="B").update(40)
    _bar(second, total=100, unit="B").update(10)

    assert (first_seen[-1], second_seen[-1]) == (40, 10)
