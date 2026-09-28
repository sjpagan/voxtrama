"""`.env` reaches the containers, not only compose's own `${...}`.

Before this, compose.yaml had no `env_file:`: each service saw only the
variables it listed by name, and `VOXTRAMA_OLLAMA_URL`, `VOXTRAMA_OLLAMA_AUTH`,
`VOXTRAMA_PROVIDERS` and the rest, documented in `.env.example`, were
silently ignored. A remote summary model could not be configured at all
under Docker.

Read as YAML, without Docker: the CI image has none. `docker compose
config` was checked by hand.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "compose.yaml"
APPLICATION_SERVICES = ("migrate", "web", "worker")


def _services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_every_application_service_reads_the_same_optional_env_file() -> None:
    """One value everywhere, and a checkout with no .env still starts."""
    services = _services()
    for name in APPLICATION_SERVICES:
        assert services[name].get("env_file") == [{"path": ".env", "required": False}], name


def test_the_data_directory_inside_stays_data() -> None:
    """`environment:` outranks `env_file:`: a host path in .env is never used inside."""
    services = _services()
    for name in APPLICATION_SERVICES:
        assert services[name]["environment"]["VOXTRAMA_DATA_DIR"] == "/data", name


def test_the_host_is_reachable_by_name_on_docker_engine_too() -> None:
    """The setup looks for Ollama at host.docker.internal: Docker Desktop's name only."""
    services = _services()
    for name in ("web", "worker"):
        assert "host.docker.internal:host-gateway" in services[name].get("extra_hosts", []), name
