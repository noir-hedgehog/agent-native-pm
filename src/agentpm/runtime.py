from __future__ import annotations

import os
from typing import Any

from .adapters.dev import DevAgentAdapter, DevPlaneWritebackAdapter
from .adapters.hermes import HermesAdapter, HermesAdapterConfig
from .adapters.openclaw import HttpOpenClawTransport, OpenClawAdapter, OpenClawAdapterConfig
from .adapters.plane import HttpPlaneTransport, PlaneWritebackAdapter
from .orchestrator import AssignmentOrchestrator
from .persistence.sqlite_store import SqliteStore
from .store import InMemoryStore, Store


def build_store_from_env() -> Store:
    backend = os.environ.get("AGENTPM_STORE", "memory").lower()
    if backend == "sqlite":
        db_path = os.environ.get("AGENTPM_SQLITE_PATH", ".agentpm/agentpm.sqlite3")
        store = SqliteStore(db_path)
        store.run_migrations()
        return store
    if backend in {"memory", "inmemory"}:
        return InMemoryStore()
    raise ValueError(f"unsupported AGENTPM_STORE={backend}")


def build_agent_adapter_from_env() -> Any:
    provider = os.environ.get("AGENTPM_AGENT_PROVIDER", "dev").lower()
    if provider == "dev":
        return DevAgentAdapter()
    if provider == "openclaw":
        base_url = _required_env("OPENCLAW_BASE_URL")
        return OpenClawAdapter(
            HttpOpenClawTransport(
                base_url=base_url,
                token=os.environ.get("OPENCLAW_TOKEN"),
                api_key=os.environ.get("OPENCLAW_API_KEY"),
            ),
            OpenClawAdapterConfig.from_env(),
        )
    if provider == "hermes":
        base_url = _required_env("HERMES_BASE_URL")
        return HermesAdapter(
            HttpOpenClawTransport(
                base_url=base_url,
                token=os.environ.get("HERMES_TOKEN"),
                api_key=os.environ.get("HERMES_API_KEY"),
            ),
            HermesAdapterConfig.from_env(),
        )
    raise ValueError(f"unsupported AGENTPM_AGENT_PROVIDER={provider}")


def build_plane_adapter_from_env() -> Any:
    base_url = os.environ.get("PLANE_API_BASE_URL")
    if not base_url:
        return DevPlaneWritebackAdapter()
    return PlaneWritebackAdapter(
        HttpPlaneTransport.from_env(),
        max_attempts=int(os.environ.get("PLANE_WRITEBACK_MAX_ATTEMPTS", "3")),
        retry_delay_seconds=float(os.environ.get("PLANE_WRITEBACK_RETRY_DELAY_SECONDS", "0.05")),
    )


def build_assignment_orchestrator_from_env(store: Store | None = None) -> AssignmentOrchestrator:
    runtime_store = store or build_store_from_env()
    return AssignmentOrchestrator(
        store=runtime_store,
        agent_adapter=build_agent_adapter_from_env(),
        plane_adapter=build_plane_adapter_from_env(),
        secret=os.environ.get("PLANE_WEBHOOK_SECRET", "dev-secret"),
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value
