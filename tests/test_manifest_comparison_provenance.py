"""input.source_url/source_title/provenance count when they differ.

Split from test_manifest_comparison.py for the same reason
test_manifest_comparison_show_expected.py is: one file per concern, to
stay under the project's size limit. Unlike input.recording_id, the catalog
does not expect these three to differ: two runs on the same URL ground
the same audio, and a difference there is exactly what the comparison
must surface.
"""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.comparison.report import compare


def _as_url_input(manifest: dict, *, url: str, title: str) -> None:
    manifest["input"]["provenance"] = "url"
    manifest["input"]["source_url"] = url
    manifest["input"]["source_title"] = title


def test_two_runs_on_the_same_url_show_no_provenance_difference():
    a, b = manifest_dict(), manifest_dict()
    _as_url_input(a, url="https://example.com/watch?v=abc", title="A clip")
    _as_url_input(b, url="https://example.com/watch?v=abc", title="A clip")

    result = compare(a, b)

    assert result.exit_code == 0
    assert result.lines == ["No differences that count."]


def test_two_runs_on_different_urls_count_the_provenance_difference():
    a, b = manifest_dict(), manifest_dict()
    _as_url_input(a, url="https://example.com/watch?v=abc", title="A clip")
    _as_url_input(b, url="https://example.com/watch?v=xyz", title="A different clip")

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("input.source_url" in line for line in result.lines)
    assert any("input.source_title" in line for line in result.lines)
