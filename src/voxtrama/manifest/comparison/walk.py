"""The structural walker: every disagreement between two manifest dicts, unjudged.

Works on the dict two manifests parse to, not on the Manifest model: a
field added to the schema tomorrow shows up here without this file
changing, because nothing here names a field by hand.

`steps` aligns by `step_id` and `outputs` by `path` (the manifest's own keys for
each), so a step inserted in the middle or a list returned in a different
order does not shift every path after it. Any other list (none exist
today) aligns by index instead.
"""

from __future__ import annotations

from typing import Any

from voxtrama.manifest.comparison.difference import ABSENT, Difference

_KEYED_LISTS = {"steps": "step_id", "outputs": "path"}


def walk(a: dict, b: dict) -> list[Difference]:
    """Every raw Difference between manifest dicts `a` and `b`."""
    return _walk_dict(a, b, "")


def _walk_dict(a: dict, b: dict, prefix: str) -> list[Difference]:
    differences = []
    for key in sorted(set(a) | set(b)):
        path = f"{prefix}.{key}" if prefix else key
        differences.extend(_walk_value(a.get(key, ABSENT), b.get(key, ABSENT), path, key))
    return differences


def _walk_value(a_value: Any, b_value: Any, path: str, key: str | None) -> list[Difference]:
    if a_value is ABSENT or b_value is ABSENT:
        return [Difference(path, a_value, b_value)]
    if isinstance(a_value, dict) and isinstance(b_value, dict):
        return _walk_dict(a_value, b_value, path)
    if isinstance(a_value, list) and isinstance(b_value, list):
        return _walk_list(a_value, b_value, path, key)
    if a_value != b_value:
        return [Difference(path, a_value, b_value)]
    return []


def _walk_list(a_list: list, b_list: list, path: str, key: str | None) -> list[Difference]:
    key_field = _KEYED_LISTS.get(key or "")
    if key_field is not None:
        return _walk_keyed_list(a_list, b_list, path, key_field)
    differences = []
    for i in range(max(len(a_list), len(b_list))):
        a_item = a_list[i] if i < len(a_list) else ABSENT
        b_item = b_list[i] if i < len(b_list) else ABSENT
        differences.extend(_walk_value(a_item, b_item, f"{path}[{i}]", None))
    return differences


def _walk_keyed_list(a_list: list, b_list: list, path: str, key_field: str) -> list[Difference]:
    a_by_key = {item[key_field]: item for item in a_list}
    b_by_key = {item[key_field]: item for item in b_list}
    differences = []
    for item_key in sorted(set(a_by_key) | set(b_by_key)):
        differences.extend(
            _walk_value(
                a_by_key.get(item_key, ABSENT),
                b_by_key.get(item_key, ABSENT),
                f"{path}[{item_key}]",
                None,
            )
        )
    return differences
