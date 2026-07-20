from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_REGISTRY_FILE = ROOT_DIR / ".agentpm" / "plane-agent-registry.json"
DEFAULT_AGENT_APPLICATIONS_FILE = ROOT_DIR / ".agentpm" / "plane-agent-applications.json"

ROLE_GUEST = 5
ROLE_MEMBER = 15
ROLE_ADMIN = 20

ROLE_ALIASES = {
    "admin": "admin",
    "administrator": "admin",
    "coordinator": "admin",
    "member": "member",
    "worker": "member",
    "guest": "guest",
    "observer": "guest",
}

ROLE_PROFILES: dict[str, dict[str, Any]] = {
    "admin": {
        "workspace_role": ROLE_ADMIN,
        "project_role": ROLE_ADMIN,
        "role_name": "Admin / Coordinator",
        "capabilities": (
            "read",
            "comment",
            "update_status",
            "assign",
            "create_project",
            "create_work_item",
            "manage_project_members",
        ),
    },
    "member": {
        "workspace_role": ROLE_MEMBER,
        "project_role": ROLE_MEMBER,
        "role_name": "Member / Worker",
        "capabilities": ("read", "comment", "update_status", "create_work_item"),
    },
    "guest": {
        "workspace_role": ROLE_GUEST,
        "project_role": ROLE_GUEST,
        "role_name": "Guest / Observer",
        "capabilities": ("read", "comment"),
    },
}

READ_CAPABILITIES = ("read", "comment", "update_status", "assign")


@dataclass(frozen=True)
class AgentAccount:
    agent_id: str
    display_name: str
    email: str
    username: str
    workspace_role: int
    project_role: int
    role_name: str
    capabilities: tuple[str, ...]
    plane_user_id: str | None = None
    token: str | None = None
    source: str = "default"

    @property
    def public_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "email": self.email,
            "username": self.username,
            "workspace_role": self.workspace_role,
            "project_role": self.project_role,
            "role_name": self.role_name,
            "capabilities": list(self.capabilities),
            "plane_user_id": self.plane_user_id,
            "has_token": bool(self.token),
            "source": self.source,
        }


DEFAULT_AGENT_SPECS: dict[str, AgentAccount] = {
    "hekate": AgentAccount(
        agent_id="hekate",
        display_name="Hekate",
        email="agent-hekate@agentpm.local",
        username="agent-hekate",
        workspace_role=20,
        project_role=20,
        role_name="Admin / Coordinator",
        capabilities=ROLE_PROFILES["admin"]["capabilities"],
    ),
    "iris": AgentAccount(
        agent_id="iris",
        display_name="Iris",
        email="agent-iris@agentpm.local",
        username="agent-iris",
        workspace_role=15,
        project_role=15,
        role_name="Member / Worker",
        capabilities=ROLE_PROFILES["member"]["capabilities"],
    ),
    "lingxi": AgentAccount(
        agent_id="lingxi",
        display_name="Lingxi",
        email="agent-lingxi@agentpm.local",
        username="agent-lingxi",
        workspace_role=15,
        project_role=15,
        role_name="Member / Worker",
        capabilities=ROLE_PROFILES["member"]["capabilities"],
    ),
    "taichi": AgentAccount(
        agent_id="taichi",
        display_name="Taichi",
        email="agent-taichi@agentpm.local",
        username="agent-taichi",
        workspace_role=5,
        project_role=5,
        role_name="Guest / Observer",
        capabilities=ROLE_PROFILES["guest"]["capabilities"],
    ),
}


class AgentAccountRegistry:
    def __init__(self, accounts: Mapping[str, AgentAccount], *, default_agent_id: str = "hekate") -> None:
        self._accounts = dict(accounts)
        self.default_agent_id = default_agent_id

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        env_file: str | Path | None = None,
        registry_file: str | Path | None = None,
    ) -> "AgentAccountRegistry":
        values = dict(os.environ if env is None else env)
        values.update({key: value for key, value in _read_agent_env_file(env_file).items() if key not in values})

        token_map = _load_json_mapping(values.get("PLANE_AGENT_TOKEN_MAP"), "PLANE_AGENT_TOKEN_MAP")
        user_map = _load_json_mapping(values.get("PLANE_AGENT_USER_MAP"), "PLANE_AGENT_USER_MAP")
        registry_specs = load_agent_registry(registry_file, env=values)

        accounts: dict[str, AgentAccount] = {}
        for agent_id, account in {**DEFAULT_AGENT_SPECS, **registry_specs}.items():
            user_info = _mapping_value(user_map, agent_id)
            token_info = _mapping_value(token_map, agent_id)
            accounts[agent_id] = replace(
                account,
                plane_user_id=_first_string(user_info, ("id", "user_id", "plane_user_id"), default=account.plane_user_id),
                email=_first_string(user_info, ("email",), default=account.email) or account.email,
                username=_first_string(user_info, ("username",), default=account.username) or account.username,
                display_name=_first_string(user_info, ("display_name", "name"), default=account.display_name)
                or account.display_name,
                token=_token_value(token_info),
            )

        default_agent_id = values.get("PLANE_MCP_AGENT_ID") or values.get("AGENTPM_DEFAULT_AGENT_ID") or "hekate"
        return cls(accounts, default_agent_id=default_agent_id)

    def list_accounts(self) -> list[AgentAccount]:
        return [self._accounts[key] for key in sorted(self._accounts)]

    def get(self, agent_id: str | None = None) -> AgentAccount:
        resolved_id = agent_id or self.default_agent_id
        account = self._accounts.get(resolved_id)
        if account is None:
            known = ", ".join(sorted(self._accounts))
            raise ValueError(f"unknown agent_id: {resolved_id}; known agents: {known}")
        return account

    def resolve_assignee(self, assignee: str | None) -> AgentAccount | None:
        if not assignee:
            return None
        normalized = str(assignee).strip().lower()
        if normalized in self._accounts:
            return self._accounts[normalized]
        for account in self._accounts.values():
            candidates = {
                account.agent_id.lower(),
                account.email.lower(),
                account.username.lower(),
            }
            if account.plane_user_id:
                candidates.add(account.plane_user_id.lower())
            if normalized in candidates:
                return account
        return None

    def require_capability(self, account: AgentAccount, capability: str) -> None:
        if capability not in account.capabilities:
            raise PermissionError(f"agent_id={account.agent_id} is not allowed to {capability}")

    def public_accounts(self) -> list[dict[str, Any]]:
        return [account.public_dict for account in self.list_accounts()]

    def agent_ids(self) -> list[str]:
        return sorted(self._accounts)


def load_agent_registry(
    registry_file: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, AgentAccount]:
    path = _registry_path(registry_file, env=env)
    if not path.exists():
        return {}
    payload = _load_json_file(path)
    rows = payload.get("agents", payload)
    if isinstance(rows, Mapping):
        iterator = rows.items()
    elif isinstance(rows, list):
        iterator = ((_agent_id_from_row(row), row) for row in rows if isinstance(row, Mapping))
    else:
        raise ValueError(f"{path} must contain an agents object or list")

    accounts: dict[str, AgentAccount] = {}
    for raw_agent_id, raw_spec in iterator:
        if not isinstance(raw_spec, Mapping):
            continue
        agent_id = normalize_agent_id(str(raw_spec.get("agent_id") or raw_agent_id))
        if not agent_id:
            continue
        accounts[agent_id] = agent_account_from_spec(agent_id, raw_spec, source=str(raw_spec.get("source") or "registry"))
    return accounts


def write_agent_registry(
    accounts: Mapping[str, AgentAccount],
    registry_file: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    path = _registry_path(registry_file, env=env)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agents": {
            agent_id: {
                "agent_id": account.agent_id,
                "display_name": account.display_name,
                "email": account.email,
                "username": account.username,
                "workspace_role": account.workspace_role,
                "project_role": account.project_role,
                "role_name": account.role_name,
                "capabilities": list(account.capabilities),
                "plane_user_id": account.plane_user_id,
                "source": account.source,
            }
            for agent_id, account in sorted(accounts.items())
        }
    }
    _write_json_file(path, payload)
    return path


def upsert_agent_registry_account(
    account: AgentAccount,
    registry_file: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    accounts = load_agent_registry(registry_file, env=env)
    accounts[account.agent_id] = account
    return write_agent_registry(accounts, registry_file, env=env)


def agent_account_from_spec(agent_id: str, spec: Mapping[str, Any], *, source: str = "registry") -> AgentAccount:
    role_key = normalize_role(str(spec.get("requested_role") or spec.get("role") or spec.get("role_key") or "member"))
    profile = ROLE_PROFILES[role_key]
    display_name = str(spec.get("display_name") or spec.get("name") or agent_id.replace("-", " ").title())
    email = str(spec.get("email") or default_agent_email(agent_id))
    username = str(spec.get("username") or f"agent-{agent_id}")
    workspace_role = int(spec.get("workspace_role") or profile["workspace_role"])
    project_role = int(spec.get("project_role") or profile["project_role"])
    role_name = str(spec.get("role_name") or profile["role_name"])
    capabilities = tuple(str(value) for value in spec.get("capabilities") or profile["capabilities"])
    return AgentAccount(
        agent_id=agent_id,
        display_name=display_name,
        email=email,
        username=username,
        workspace_role=workspace_role,
        project_role=project_role,
        role_name=role_name,
        capabilities=capabilities,
        plane_user_id=_first_string(spec, ("plane_user_id", "user_id", "id")),
        token=_token_value(spec),
        source=source,
    )


def normalize_agent_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return normalized


def default_agent_email(agent_id: str) -> str:
    return f"agent-{agent_id}@agentpm.local"


def normalize_role(value: str | None) -> str:
    if not value:
        return "member"
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    role = ROLE_ALIASES.get(normalized)
    if not role:
        allowed = ", ".join(sorted(ROLE_PROFILES))
        raise ValueError(f"unknown agent role: {value}; allowed roles: {allowed}")
    return role


def role_profile(role: str | None) -> dict[str, Any]:
    return ROLE_PROFILES[normalize_role(role)]


def extract_assignee_ids(item: Mapping[str, Any]) -> set[str]:
    assignee_ids: set[str] = set()

    for key in ("assignee_ids", "assignees"):
        value = item.get(key)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, str):
                    assignee_ids.add(row)
                elif isinstance(row, Mapping):
                    row_id = row.get("id") or row.get("user_id") or row.get("member_id")
                    if row_id:
                        assignee_ids.add(str(row_id))

    assignee = item.get("assignee")
    if isinstance(assignee, str):
        assignee_ids.add(assignee)
    elif isinstance(assignee, Mapping):
        row_id = assignee.get("id") or assignee.get("user_id") or assignee.get("member_id")
        if row_id:
            assignee_ids.add(str(row_id))

    assignee_details = item.get("assignee_details")
    if isinstance(assignee_details, list):
        for row in assignee_details:
            if isinstance(row, Mapping) and row.get("id"):
                assignee_ids.add(str(row["id"]))

    return assignee_ids


def _read_agent_env_file(env_file: str | Path | None) -> dict[str, str]:
    path = Path(env_file) if env_file else Path(os.environ.get("AGENTPM_PLANE_AGENT_ENV_FILE", ".agentpm/plane-agent-env.sh"))
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("export "):
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            continue
        for part in parts[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            values[key] = value
    return values


def _load_json_mapping(raw: str | None, name: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object")
    return parsed


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} must contain valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _registry_path(registry_file: str | Path | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    raw = registry_file or values.get("AGENTPM_PLANE_AGENT_REGISTRY_FILE") or DEFAULT_AGENT_REGISTRY_FILE
    return Path(raw)


def _agent_id_from_row(row: Mapping[str, Any]) -> str:
    return str(row.get("agent_id") or row.get("id") or row.get("username") or "")


def _mapping_value(mapping: Mapping[str, Any], agent_id: str) -> Any:
    return mapping.get(agent_id) or mapping.get(agent_id.lower()) or mapping.get(agent_id.upper())


def _first_string(value: Any, keys: tuple[str, ...], default: str | None = None) -> str | None:
    if isinstance(value, Mapping):
        for key in keys:
            found = value.get(key)
            if found:
                return str(found)
    return default


def _token_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        token = value.get("token") or value.get("api_token") or value.get("PLANE_API_TOKEN")
        return str(token) if token else None
    return None
