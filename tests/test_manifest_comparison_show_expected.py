"""`--show-expected`'s two rendering branches: the catalog, and the determinism gate.

Split from test_manifest_comparison.py, which already covers exit codes and
classification: this file is only about what changes on the report when the
flag turns a count into a listed diff, for each of the two reasons a
difference can be expected.
"""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.comparison.report import compare


def test_show_expected_lists_catalog_differences_instead_of_counting_them():
    a, b = manifest_dict(), manifest_dict()
    b["run"]["id"] = "run-2"

    result = compare(a, b, show_expected=True)

    assert "Expected differences ignored (identifiers, times):" in result.lines
    assert any("run.id" in line for line in result.lines)
    assert not any(line.startswith("1 expected difference") for line in result.lines)


def test_show_expected_lists_gated_differences_with_their_reason():
    """`outputs[0].sha256` used to be the gated field driving this test.

    That field moved to the catalog unconditionally (it always
    embeds a run id, so it is never a question of determinism) and moved
    the gated question to the per-step `output_sha256` instead
    (comparison/determinism.py's docstring). This test now drives that
    field, on "summarize", which the default fixture makes non_deterministic.
    """
    a, b = manifest_dict(), manifest_dict()
    b["steps"][1]["output_sha256"] = "1" * 64

    result = compare(a, b, show_expected=True)

    gated_line = "  steps[summarize].output_sha256: "
    reason = "(step 'summarize' is non_deterministic)"
    assert "Differences ignored as non-reproducible:" in result.lines
    assert any(line.startswith(gated_line) and line.endswith(reason) for line in result.lines)
    assert not any(line.startswith("1 difference ignored") for line in result.lines)
