"""steps[].model/.provider/.host count in `voxtrama compare`.

Split from test_manifest_comparison.py for the same reason
test_manifest_comparison_provenance.py is: one concern per file. The project
holds that two runs on different models or hosts are not two runs
confirming the same thing. walk.py already treats these as any other
field, so these tests prove that nothing in difference.py's
catalog was taught to look away from them.
"""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.comparison.report import compare


def test_two_runs_on_the_same_model_show_no_difference_there():
    a, b = manifest_dict(), manifest_dict()

    result = compare(a, b)

    assert result.exit_code == 0
    assert result.lines == ["No differences that count."]


def test_a_different_model_on_the_same_step_counts():
    a, b = manifest_dict(), manifest_dict()
    b["steps"][1]["model"] = "a-different-model"

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[summarize].model" in line for line in result.lines)


def test_a_different_host_on_the_same_step_counts():
    a, b = manifest_dict(), manifest_dict()
    b["steps"][1]["host"] = "remote.example.com"

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[summarize].host" in line for line in result.lines)
