"""The two ManifestStep fixtures every test manifest carries.

Split out of fakes.manifest once ManifestChoices/ManifestRun gained new
fields to set there, tipping that file past the project's line limit.
"""

from __future__ import annotations

from voxtrama.manifest.schema import ManifestStep
from voxtrama.workflow.skill import Determinism


def transcribe_step() -> ManifestStep:
    """The extractive step every test manifest carries: same_host, in-process, no remote host.

    Split out of `steps` (the project's function-length limit), one function
    per step rather than the two compressed into one: provenance gave each step
    five more fields to set.
    """
    return ManifestStep(
        step_id="transcribe",
        skill="transcribe",
        skill_version="1.0.0",
        state="succeeded",
        deterministic=Determinism.SAME_HOST,
        attempts=1,
        position=0,
        started_at="t1",
        finished_at="t1b",
        error=None,
        duration_seconds=1.0,
        output_sha256="b" * 64,
        model="whisper",
        model_revision="rev-1",
        provider="local",
        host=None,
        profile_check_skipped=False,
        input_sha256="f" * 64,
        reuse_key="g" * 64,
        reused_from_run_id=None,
        context_window_tokens=None,
        context_window_at_risk=None,
        output_resumptions=None,
    )


def summarize_step(*, deterministic: Determinism) -> ManifestStep:
    """The generative step every test manifest carries, behind a remote Ollama."""
    return ManifestStep(
        step_id="summarize",
        skill="summarize",
        skill_version="1.0.0",
        state="succeeded",
        deterministic=deterministic,
        attempts=1,
        position=1,
        started_at="t1c",
        finished_at="t2",
        error=None,
        duration_seconds=2.0,
        output_sha256="c" * 64,
        model="qwen-test",
        model_revision="sha256:x",
        provider="ollama",
        host="127.0.0.1:11434",
        profile_check_skipped=False,
        input_sha256="h" * 64,
        reuse_key="i" * 64,
        reused_from_run_id=None,
        context_window_tokens=8192,
        context_window_at_risk=False,
        output_resumptions=0,
    )


def build_steps(*, all_same_host: bool = False) -> list[ManifestStep]:
    """The two steps every test manifest carries.

    By default "summarize" is non_deterministic, the shape any workflow
    with a generative skill has (workflow.skill's own
    ModelClass.GENERATIVE -> Determinism.NON_DETERMINISTIC). With
    `all_same_host=True`, both steps are same_host instead: the one other
    state the determinism gate can find in a manifest a real, entirely
    extractive workflow could produce.
    """
    second = Determinism.SAME_HOST if all_same_host else Determinism.NON_DETERMINISTIC
    return [transcribe_step(), summarize_step(deterministic=second)]
