"""Settings › Data & privacy: where the data lives, what leaves.

Shown, never applied: the rules themselves are retention, the
provider choice and `local_only`. A person opens this page
and knows, without asking anyone, where their files are, how much room
they take, and for every step of every workflow whether its content stays
in Voxtrama, goes to a model server on this machine, or leaves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.catalog import list_workflow_names, load_named_workflow
from voxtrama.humanize import human_bytes
from voxtrama.providers.registry import LOCAL, configured_providers, provider_named
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.privacy import declared_local_only
from voxtrama.workflow.skill import ModelClass, Privacy

# What happens to a step's content (the page words each):
IN_APP = "in_app"  # transcribe, diarize: inside Voxtrama itself
LOCAL_SERVER = "local"  # a model server on this machine
LEAVES = "leaves"  # a remote model server
REFUSED = "refused"  # kept local, and the server is remote: the job is refused
NO_SERVER = "no_server"


@dataclass(frozen=True)
class Area:
    key: str  # recordings, runs, models, database
    path: str
    size: int

    @property
    def label(self) -> str:
        return human_bytes(self.size)


@dataclass(frozen=True)
class Server:
    name: str
    host: str
    locality: str
    default: bool


@dataclass(frozen=True)
class StepRoute:
    skill: str
    where: str
    server: str | None
    kept_by: str | None


@dataclass(frozen=True)
class WorkflowRoute:
    name: str
    title: str
    steps: tuple[StepRoute, ...]


@dataclass(frozen=True)
class PrivacyView:
    data_dir: str
    areas: tuple[Area, ...]
    servers: tuple[Server, ...]
    workflows: tuple[WorkflowRoute, ...]


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def _areas(data_dir: Path) -> tuple[Area, ...]:
    paths = get_paths(data_dir)
    places = (
        ("recordings", paths.recordings_dir),
        ("runs", paths.runs_dir),
        ("models", paths.models_dir),
        ("database", paths.db_path),
    )
    return tuple(Area(key, str(path), _size(path)) for key, path in places)


def _route(workflow: Workflow, settings: Settings) -> WorkflowRoute:
    server = provider_named(settings, None)
    steps = []
    for step in workflow.steps:
        skill = BUILTIN_SKILLS.get(step.skill, {}).get(step.skill_version)
        if skill is None or skill.model_class != ModelClass.GENERATIVE:
            steps.append(StepRoute(step.skill, IN_APP, None, None))
            continue
        own = f"skill {skill.name}" if skill.privacy == Privacy.LOCAL_ONLY else None
        kept_by = own or declared_local_only(workflow, step)
        if server is None:
            where = NO_SERVER
        elif server.locality == LOCAL:
            where = LOCAL_SERVER
        else:
            where = REFUSED if kept_by else LEAVES
        steps.append(StepRoute(step.skill, where, server.name if server else None, kept_by))
    return WorkflowRoute(workflow.name, workflow.title or workflow.name, tuple(steps))


def privacy_view(settings: Settings) -> PrivacyView:
    """Everything the page shows, read now."""
    default = provider_named(settings, None)
    servers = tuple(
        Server(p.name, p.url.split("//")[-1].split("/")[0], p.locality, p.name == default.name)
        for p in configured_providers(settings).values()
    )
    workflows = []
    for name in list_workflow_names():
        try:
            workflows.append(_route(load_named_workflow(name), settings))
        except Exception:  # a broken custom file: the Workflows page says why
            continue
    return PrivacyView(str(settings.data_dir), _areas(settings.data_dir), servers, tuple(workflows))
