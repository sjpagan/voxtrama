"""What the «Regenerate job» panel starts from.

Regenerate reruns the job, optionally with changed settings. It shows the
same fields as the new-job form (components/job_fields.html), filled in
with what this job ran with instead of the installation's defaults, so
regenerating without touching anything reruns the same job. The field
names match api.routes.job_defaults.JobDefaults so the template macro
that draws them reads either.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegenerateForm:
    workflows: tuple[tuple[str, str], ...]  # (name, title), as the new-job form lists them
    workflow_name: str
    context: str
    hardware_profile: str
    parallel_chunks: int
    cores_per_chunk: int
    generative_model: str | None
    summary_detail: int
    pause_merge_seconds: float
    machine_cores: int | None
    output_language: str
    retention_days: str
    installation_retention_days: int | None
    providers: tuple[tuple[str, str], ...]
    provider: str
    whisper_models: tuple[tuple[str, str], ...]
    llm_models: tuple[str, ...]
