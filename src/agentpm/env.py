from __future__ import annotations

import os
from typing import Mapping


def mesh_env(name: str, default: str | None = None, *, env: Mapping[str, str] | None = None) -> str | None:
    """Read a Mesh setting while preserving one release of AGENTPM compatibility."""
    values = os.environ if env is None else env
    mesh_name = name if name.startswith("MESH_") else f"MESH_{name}"
    legacy_name = name if name.startswith("AGENTPM_") else f"AGENTPM_{name}"
    return values.get(mesh_name, values.get(legacy_name, default))


def mesh_env_bool(name: str, default: bool = False, *, env: Mapping[str, str] | None = None) -> bool:
    value = mesh_env(name, env=env)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
