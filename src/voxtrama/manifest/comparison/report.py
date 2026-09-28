"""Reads two manifests, compares them, and renders the report `voxtrama compare` prints.

Rendering lives here, not in the CLI, because a comparison has exactly one
correct wording (manifests are promised to be diffable) and comparison is the
only feature that needs it: cli/commands/compare.py only echoes the lines
this returns and turns `exit_code` into a `typer.Exit`. It never imports
typer, so core still does not depend on the entrypoint that uses it.
See the module docstring of manifest/comparison/__init__.py.

Deciding which bucket a Difference lands in is classify.py's job, not
this file's (split out to stay under the project's line limit): this
file only walks the two manifests, calls classify(), and turns its three
buckets into text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from voxtrama.manifest.comparison.classify import classify
from voxtrama.manifest.comparison.difference import ABSENT, Difference
from voxtrama.manifest.comparison.walk import walk
from voxtrama.manifest.schema import Manifest

_VALUE_TRUNCATE = 60


class ManifestReadError(Exception):
    """A manifest could not be turned into a dict to compare: unreadable, not JSON, or invalid."""


@dataclass(frozen=True)
class CompareResult:
    """What `voxtrama compare` should print, and the exit code that goes with it."""

    lines: list[str]
    exit_code: int


def load_manifest(path: Path) -> dict:
    """Read `path` as JSON. Raises ManifestReadError. Does not validate against Manifest yet.

    Validation is deferred to `compare`, because a manifest_version
    mismatch must be reported on its own (see its docstring) rather than
    fail schema validation first: Manifest only accepts today's version.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ManifestReadError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestReadError(f"invalid JSON in {path}: {exc}") from exc


def compare(a: dict, b: dict, *, show_expected: bool = False) -> CompareResult:
    """Compare two already-parsed manifest dicts and build the report.

    A `manifest_version` mismatch short-circuits everything else: it is
    reported as the sole difference, at exit code 1, with no field-by-field
    walk: the two shapes are not guaranteed comparable at all. Equal but
    unsupported versions fail Manifest validation instead, at exit code 2.
    """
    if a.get("manifest_version") != b.get("manifest_version"):
        diff = Difference("manifest_version", a.get("manifest_version"), b.get("manifest_version"))
        return CompareResult(lines=["Differences that count:", f"  {_render(diff)}"], exit_code=1)
    _validate(a)
    _validate(b)
    counted, expected, gated = classify(walk(a, b), a, b)
    lines = _render_report(counted, expected, gated, show_expected)
    return CompareResult(lines=lines, exit_code=1 if counted else 0)


def _validate(manifest: dict) -> None:
    try:
        Manifest.model_validate(manifest)
    except ValidationError as exc:
        raise ManifestReadError(f"manifest does not match the schema: {exc}") from exc


def _render_report(
    counted: list[Difference],
    expected: list[Difference],
    gated: list[tuple[Difference, str]],
    show_expected: bool,
) -> list[str]:
    if counted:
        lines = ["Differences that count:"] + [f"  {_render(d)}" for d in counted]
    else:
        lines = ["No differences that count."]
    lines += _render_expected(expected, show_expected)
    lines += _render_gated(gated, show_expected)
    return lines


def _render_expected(differences: list[Difference], show_expected: bool) -> list[str]:
    if not differences:
        return []
    if show_expected:
        return ["Expected differences ignored (identifiers, times):"] + [
            f"  {_render(d)}" for d in differences
        ]
    noun = "difference" if len(differences) == 1 else "differences"
    return [f"{len(differences)} expected {noun} ignored (identifiers, times)."]


def _render_gated(gated: list[tuple[Difference, str]], show_expected: bool) -> list[str]:
    """Render the gated bucket, one reason per Difference (reasons no longer share one).

    `--show-expected` still groups them under one heading, but each line
    now names its own reason, because two gated differences in the same
    report can be open for two different steps.
    """
    if not gated:
        return []
    if show_expected:
        return ["Differences ignored as non-reproducible:"] + [
            f"  {_render(d)} ({reason})" for d, reason in gated
        ]
    noun = "difference" if len(gated) == 1 else "differences"
    reasons = "; ".join(dict.fromkeys(reason for _, reason in gated))
    return [f"{len(gated)} {noun} ignored as non-reproducible: {reasons}."]


def _render(diff: Difference) -> str:
    return f"{diff.path}: {_render_value(diff.before)} -> {_render_value(diff.after)}"


def _render_value(value: Any) -> str:
    if value is ABSENT:
        return "(absent)"
    text = json.dumps(value)
    return text if len(text) <= _VALUE_TRUNCATE else f"{text[:_VALUE_TRUNCATE]}..."
