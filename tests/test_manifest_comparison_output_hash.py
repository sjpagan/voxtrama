"""The per-step output hash gate, `steps[<id>].output_sha256`, and outputs[*].sha256's fix.

Split from test_manifest_comparison.py, which already covers exit codes and
the catalog of differences. This file is only about whether *this*
step's own output hash counts, judged against only its own determinism
(comparison/determinism.py's output_hash_reason), and the proof that
outputs[*].sha256 (the envelope hash the bug lived in) never counts at
all anymore.
"""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.comparison.report import compare


def test_output_hash_counts_when_every_step_is_same_host():
    """This used to change outputs[0].sha256 and expect it to count.

    That was the bug: outputs[].sha256 hashes output.json, which embeds
    run_id (manifest/output.py), so it differs between *any* two runs and
    can never legitimately count (comparison/difference.py's catalog now
    says so unconditionally). The reachable equivalent of "every step
    deterministic" this test means to cover is an entirely extractive
    workflow, both steps same_host (workflow.skill's
    ModelClass.EXTRACTIVE -> Determinism.SAME_HOST) on identical hardware.
    That is now steps[<id>].output_sha256: the per-step hash,
    and the one this gate now judges. No Skill in this repo can emit
    the literal `deterministic` value today. See
    test_manifest_comparison.py's test_a_deterministic_step_value_does_not_open_the_gate,
    which covers that value directly rather than through a manifest no
    builder could ever produce.
    """
    a, b = manifest_dict(all_same_host=True), manifest_dict(all_same_host=True)
    b["steps"][0]["output_sha256"] = "1" * 64

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[transcribe].output_sha256" in line for line in result.lines)


def test_outputs_envelope_sha256_never_counts():
    """The fix: outputs[*].sha256 is
    expected no matter what the gate would otherwise say, even here,
    where every step is same_host on identical hardware and would leave
    the gate closed for anything else.
    """
    a, b = manifest_dict(all_same_host=True), manifest_dict(all_same_host=True)
    b["outputs"][0]["sha256"] = "1" * 64

    result = compare(a, b)
    shown = compare(a, b, show_expected=True)

    assert result.exit_code == 0
    assert result.lines[0] == "No differences that count."
    assert any("outputs[output.json].sha256" in line for line in shown.lines)


def test_step_output_hash_is_expected_when_that_step_is_non_deterministic():
    a, b = manifest_dict(), manifest_dict()
    b["steps"][1]["output_sha256"] = "1" * 64

    result = compare(a, b)

    assert result.exit_code == 0
    reason_lines = [line for line in result.lines if "non-reproducible" in line]
    assert len(reason_lines) == 1
    assert "summarize" in reason_lines[0]


def test_extractive_step_output_hash_still_counts_next_to_a_non_deterministic_step():
    """The tightened gate, proven in one run.

    "summarize" is non_deterministic in the default fixture, so its own
    hash difference is gated, but "transcribe" is same_host on identical
    hardware, and its hash difference counts anyway. Before the fix a single
    non_deterministic step opened the gate on every step's output; now it
    only opens its own.
    """
    a, b = manifest_dict(), manifest_dict()
    b["steps"][0]["output_sha256"] = "1" * 64
    b["steps"][1]["output_sha256"] = "2" * 64

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[transcribe].output_sha256" in line for line in result.lines)
    assert not any("steps[summarize].output_sha256" in line for line in result.lines)


def test_step_output_hash_counts_when_deterministic_is_none():
    """`deterministic == None` is not a license to vary (determinism.py's
    own rule): a step whose skill could not be resolved must still match.
    """
    a, b = manifest_dict(), manifest_dict()
    a["steps"][1]["deterministic"] = None
    b["steps"][1]["deterministic"] = None
    b["steps"][1]["output_sha256"] = "1" * 64

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[summarize].output_sha256" in line for line in result.lines)
