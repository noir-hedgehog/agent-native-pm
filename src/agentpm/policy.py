from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_ALLOWED_ACTIONS = ("read_plane", "comment", "update_status", "create_work_item")
DEFAULT_TIMEOUTS = {"reminder": 24, "block": 72}


@dataclass(frozen=True)
class ProjectPolicyInput:
    project_id: str
    pipeline_definition: list[str]
    agent_profile_by_role: dict[str, str]
    transition_approval_rules: dict[str, bool]
    transition_timeout_hours: dict[str, int]
    allowed_actions_by_role: dict[str, list[str]]
    published_by: str
    change_note: str | None = None


def policy_input_from_payload(project_id: str, payload: Mapping[str, Any]) -> ProjectPolicyInput:
    pipeline = [str(role).strip() for role in payload.get("pipeline_definition") or [] if str(role).strip()]
    agent_profile_by_role = {
        str(role).strip(): str(agent).strip()
        for role, agent in (payload.get("agent_profile_by_role") or {}).items()
        if str(role).strip() and str(agent).strip()
    }
    transition_rules = {
        str(key).strip(): bool(value) for key, value in (payload.get("transition_approval_rules") or {}).items()
    }
    raw_timeouts = payload.get("transition_timeout_hours") or DEFAULT_TIMEOUTS
    timeouts = {
        "reminder": int(raw_timeouts.get("reminder", DEFAULT_TIMEOUTS["reminder"])),
        "block": int(raw_timeouts.get("block", DEFAULT_TIMEOUTS["block"])),
    }
    allowed_actions = {
        str(role).strip(): [str(action).strip() for action in actions if str(action).strip()]
        for role, actions in (payload.get("allowed_actions_by_role") or {}).items()
        if str(role).strip() and isinstance(actions, list)
    }
    policy = ProjectPolicyInput(
        project_id=project_id,
        pipeline_definition=pipeline,
        agent_profile_by_role=agent_profile_by_role,
        transition_approval_rules=transition_rules,
        transition_timeout_hours=timeouts,
        allowed_actions_by_role=allowed_actions,
        published_by=str(payload.get("published_by") or "human-admin"),
        change_note=str(payload["change_note"]) if payload.get("change_note") else None,
    )
    validate_project_policy(policy)
    return policy


def default_project_policy(project_id: str, *, agent_profile: str) -> ProjectPolicyInput:
    return ProjectPolicyInput(
        project_id=project_id,
        pipeline_definition=["coder"],
        agent_profile_by_role={"coder": agent_profile},
        transition_approval_rules={"coder->done": False},
        transition_timeout_hours=dict(DEFAULT_TIMEOUTS),
        allowed_actions_by_role={"coder": list(DEFAULT_ALLOWED_ACTIONS)},
        published_by="system-fallback",
        change_note="Generated fallback policy",
    )


def validate_project_policy(policy: ProjectPolicyInput) -> None:
    roles = policy.pipeline_definition
    if not roles:
        raise ValueError("pipeline_definition must contain at least one role")
    if len(set(roles)) != len(roles):
        raise ValueError("pipeline_definition cannot contain duplicate roles")

    missing_agents = [role for role in roles if not policy.agent_profile_by_role.get(role)]
    if missing_agents:
        raise ValueError(f"agent_profile_by_role missing roles: {', '.join(missing_agents)}")

    missing_actions = [role for role in roles if role not in policy.allowed_actions_by_role]
    if missing_actions:
        raise ValueError(f"allowed_actions_by_role missing roles: {', '.join(missing_actions)}")
    empty_actions = [role for role in roles if not policy.allowed_actions_by_role.get(role)]
    if empty_actions:
        raise ValueError(f"allowed_actions_by_role must include at least one action for: {', '.join(empty_actions)}")

    allowed_transition_keys = transition_keys_for_pipeline(roles)
    invalid_keys = sorted(set(policy.transition_approval_rules) - allowed_transition_keys)
    if invalid_keys:
        raise ValueError(f"invalid transition_approval_rules keys: {', '.join(invalid_keys)}")

    reminder = policy.transition_timeout_hours.get("reminder")
    block = policy.transition_timeout_hours.get("block")
    if reminder is None or block is None:
        raise ValueError("transition_timeout_hours must include reminder and block")
    if int(reminder) <= 0 or int(block) <= 0:
        raise ValueError("transition_timeout_hours values must be positive")
    if int(block) <= int(reminder):
        raise ValueError("transition_timeout_hours.block must be greater than reminder")


def transition_keys_for_pipeline(roles: list[str]) -> set[str]:
    keys = {f"{roles[index]}->{roles[index + 1]}" for index in range(len(roles) - 1)}
    keys.add(f"{roles[-1]}->done")
    return keys
