"""voxtrama compare's core, exercised through report.compare() (verification items 1-8).

test_cli_compare.py covers item 9 (the CLI's own path resolution and exit
codes), split there because CliRunner and the Typer app belong to a
different layer than manifest.comparison, which every test here calls
directly. test_manifest_comparison_output_hash.py covers its own
verification items (the per-step output hash gate), split out to keep this
file under the project's line limit.
"""

from __future__ import annotations

from fakes.manifest import manifest_dict

from voxtrama.manifest.comparison.determinism import non_reproducible_reason
from voxtrama.manifest.comparison.report import compare


def test_identical_manifests_have_no_difference():
    result = compare(manifest_dict(), manifest_dict())

    assert result.exit_code == 0
    assert result.lines == ["No differences that count."]


def test_ids_and_times_differ_but_nothing_counts():
    """duration_seconds rides along with started_at/finished_at here.
    It is derived from them, so the same non-fact must not count twice.
    """
    a, b = manifest_dict(), manifest_dict()
    b["run"]["id"] = "run-2"
    b["run"]["created_at"] = "t0-other"
    b["run"]["destination"]["path"] = "runs/run-2"
    b["input"]["recording_id"] = "rec-2"
    b["steps"][0]["started_at"] = "later"
    b["steps"][0]["duration_seconds"] = 99.0

    result = compare(a, b)

    assert result.exit_code == 0
    assert result.lines[0] == "No differences that count."


def test_hardware_profile_used_counts():
    a, b = manifest_dict(), manifest_dict()
    b["environment"]["hardware_profile_used"] = "high"

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("environment.hardware_profile_used" in line for line in result.lines)


def test_cpu_threads_alone_counts():
    """Two runs that differ only in parallelism must stop
    comparing identical, or the diff cannot explain why one took twice
    as long as the other.
    """
    a, b = manifest_dict(), manifest_dict()
    b["environment"]["cpu_threads"] = 2

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("environment.cpu_threads" in line for line in result.lines)


def test_num_workers_alone_counts():
    a, b = manifest_dict(), manifest_dict()
    b["environment"]["num_workers"] = 1

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("environment.num_workers" in line for line in result.lines)


def test_workflow_definition_sha256_counts():
    a, b = manifest_dict(), manifest_dict()
    b["workflow"]["definition_sha256"] = "f" * 64

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("workflow.definition_sha256" in line for line in result.lines)


def test_a_step_present_in_only_one_manifest_is_named():
    a, b = manifest_dict(), manifest_dict()
    b["steps"].pop()

    result = compare(a, b)

    assert result.exit_code == 1
    assert any("steps[summarize]" in line for line in result.lines)


def test_steps_reordered_with_the_same_position_produce_no_difference():
    a, b = manifest_dict(), manifest_dict()
    b["steps"].reverse()

    result = compare(a, b)

    assert result.exit_code == 0


def test_same_host_step_on_identical_environment_does_not_open_the_gate():
    a, b = manifest_dict(all_same_host=True), manifest_dict(all_same_host=True)

    assert non_reproducible_reason(a, b) is None


def test_same_host_step_with_a_different_device_opens_the_gate():
    a, b = manifest_dict(all_same_host=True), manifest_dict(all_same_host=True)
    b["environment"]["device"] = "gpu"

    reason = non_reproducible_reason(a, b)

    assert reason == "step 'transcribe' is same_host and the two runs used different hardware"


def test_a_deterministic_step_value_does_not_open_the_gate():
    """The manifest names a third determinism value, `deterministic`, that no
    Skill in this repo can emit today (workflow.skill's own
    _MODEL_CLASS_TO_DETERMINISM has only two branches). Checked against
    the gate directly, on a step edited by hand, rather than through a
    manifest that claims to be reachable and is not.
    """
    a, b = manifest_dict(), manifest_dict()
    a["steps"][1]["deterministic"] = "deterministic"
    b["steps"][1]["deterministic"] = "deterministic"

    assert non_reproducible_reason(a, b) is None


def test_manifest_version_mismatch_is_the_only_difference_reported():
    a, b = manifest_dict(), manifest_dict()
    b["manifest_version"] = 3

    result = compare(a, b)

    assert result.exit_code == 1
    assert result.lines == ["Differences that count:", "  manifest_version: 2 -> 3"]
