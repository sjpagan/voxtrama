"""Comparing a provider's declared version to the minimum we need.

Split from ollama_probe.py by context (150 lines per file at most): this is a
pure function of two strings, with no HTTP and nothing Ollama-specific in
its logic, while everything else in that module makes a network call.
"""

from __future__ import annotations

# ollama.py's generate() sends `think: false` alongside `format: json` on
# every JSON-formatted call (either alone corrupts a thinking-capable
# model's output). Ollama only understands `think` on /api/generate from
# this release on, so this is the version our request needs to work. It is
# not a judgement of which release is "good".
MINIMUM_VERSION = "0.9.0"


def parse_version(version: str) -> tuple[int, ...] | None:
    """`version` as a tuple of ints, or None when it cannot be read that way.

    Never a string compare: the trap is that "0.34.2" sorts
    before "0.9.0" lexicographically ("3" < "9"), backwards for what these
    numbers mean. An unfamiliar format ("dev", empty, missing a part)
    returns None instead of a guess. The caller reports that as unknown,
    never as "does not meet the minimum".
    """
    parts = version.strip().split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def meets_minimum(version: str | None, minimum: str) -> bool | None:
    """Whether `version` is at least `minimum`, compared as tuples of ints.

    None is "no verdict", never "no": either `version` is None (the
    provider did not declare one) or parse_version could not read it, and
    a recommendation dressed up as either a pass or a fail is never given in
    that case.
    """
    if version is None:
        return None
    parsed, parsed_minimum = parse_version(version), parse_version(minimum)
    if parsed is None or parsed_minimum is None:
        return None
    return parsed >= parsed_minimum
