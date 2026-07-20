#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any, Mapping

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from agentpm.agent_accounts import (
    AgentAccount,
    agent_account_from_spec,
    default_agent_email,
    normalize_agent_id,
    normalize_role,
    role_profile,
    upsert_agent_registry_account,
)
from agentpm.agent_applications import AgentApplication, AgentApplicationStore


ENV_FILE = Path(os.environ.get("AGENTPM_PLANE_AGENT_ENV_FILE", ROOT_DIR / ".agentpm" / "plane-agent-env.sh"))
PLANE_DIR = Path(os.environ.get("PLANE_DIR", ROOT_DIR / "plane"))
WORKSPACE_SLUG = os.environ.get("PLANE_WORKSPACE_SLUG", "agentpm")


def main() -> None:
    parser = argparse.ArgumentParser(description="Human-admin CLI for Agent Plane account registration")
    sub = parser.add_subparsers(dest="command", required=True)

    list_apps = sub.add_parser("list-applications", help="List agent registration/project join applications")
    list_apps.add_argument("--status")

    approve = sub.add_parser("approve", help="Approve a pending application and create/update the Plane bot")
    approve.add_argument("application_id")
    approve.add_argument("--role", choices=["admin", "member", "guest"])
    approve.add_argument("--email")
    approve.add_argument("--project-id")
    approve.add_argument("--decision-reason")

    reject = sub.add_parser("reject", help="Reject a pending application")
    reject.add_argument("application_id")
    reject.add_argument("--reason", default="")

    add_agent = sub.add_parser("add-agent", help="Explicitly add an agent without a pending application")
    add_agent.add_argument("agent_id")
    add_agent.add_argument("display_name")
    add_agent.add_argument("--role", choices=["admin", "member", "guest"], default="member")
    add_agent.add_argument("--email")
    add_agent.add_argument("--project-id")

    add_project = sub.add_parser("add-to-project", help="Add an approved agent to a Plane project")
    add_project.add_argument("agent_id")
    add_project.add_argument("project_id")
    add_project.add_argument("--role", choices=["admin", "member", "guest"], default="member")

    args = parser.parse_args()
    store = AgentApplicationStore()

    if args.command == "list-applications":
        _print({"applications": [application.public_dict for application in store.list(status=args.status)]})
        return
    if args.command == "reject":
        application = store.mark(args.application_id, status="rejected", decision_reason=args.reason)
        _print({"application": application.public_dict})
        return
    if args.command == "approve":
        application = store.get(args.application_id)
        role = args.role or application.requested_role
        project_id = args.project_id if args.project_id is not None else application.project_id
        account = _approve_spec(
            {
                "agent_id": application.agent_id,
                "display_name": application.display_name,
                "email": args.email or application.email,
                "role": role,
                "source": "approved_application",
            },
            project_id=project_id,
        )
        application = store.mark(args.application_id, status="approved", decision_reason=args.decision_reason)
        _print({"application": application.public_dict, "agent": account.public_dict})
        return
    if args.command == "add-agent":
        account = _approve_spec(
            {
                "agent_id": args.agent_id,
                "display_name": args.display_name,
                "email": args.email,
                "role": args.role,
                "source": "admin_added",
            },
            project_id=args.project_id,
        )
        _print({"agent": account.public_dict})
        return
    if args.command == "add-to-project":
        role = normalize_role(args.role)
        env_values = _read_agent_env_file(ENV_FILE)
        user_map = _load_json_mapping(env_values.get("PLANE_AGENT_USER_MAP"), "PLANE_AGENT_USER_MAP")
        agent_id = normalize_agent_id(args.agent_id)
        user_info = user_map.get(agent_id)
        if not isinstance(user_info, Mapping) or not user_info.get("id"):
            raise ValueError(f"agent_id={agent_id} is missing from PLANE_AGENT_USER_MAP; approve or add it first")
        membership = _run_plane_admin(
            {"member_id": user_info["id"], "role": role_profile(role)["project_role"]},
            mode="add_to_project",
            project_id=args.project_id,
        )
        _print({"agent_id": agent_id, "project_id": args.project_id, "membership": membership})
        return
    raise AssertionError(args.command)


def _approve_spec(spec: Mapping[str, Any], *, project_id: str | None = None) -> AgentAccount:
    agent_id = normalize_agent_id(str(spec["agent_id"]))
    role = normalize_role(str(spec.get("role") or "member"))
    profile = role_profile(role)
    account_spec = {
        "agent_id": agent_id,
        "display_name": spec.get("display_name"),
        "email": spec.get("email") or default_agent_email(agent_id),
        "role": role,
        "workspace_role": profile["workspace_role"],
        "project_role": profile["project_role"],
        "role_name": profile["role_name"],
        "capabilities": profile["capabilities"],
        "source": spec.get("source") or "admin_added",
    }
    result = _run_plane_admin(account_spec, mode="approve_agent", project_id=project_id)
    user_info = result["user"]
    account = agent_account_from_spec(
        agent_id,
        {
            **account_spec,
            "plane_user_id": user_info["id"],
            "email": user_info["email"],
            "username": user_info["username"],
            "display_name": user_info["display_name"],
        },
        source=str(account_spec["source"]),
    )
    upsert_agent_registry_account(account)
    _upsert_agent_env(agent_id, user_info, result["token"])
    return account


def _run_plane_admin(spec: Mapping[str, Any], *, mode: str, project_id: str | None = None) -> dict[str, Any]:
    if not PLANE_DIR.exists():
        raise FileNotFoundError(f"Plane checkout not found at {PLANE_DIR}")
    env = {
        **os.environ,
        "AGENTPM_AGENT_ADMIN_MODE": mode,
        "AGENTPM_AGENT_ADMIN_SPEC": json.dumps(spec),
        "AGENTPM_AGENT_ADMIN_WORKSPACE_SLUG": WORKSPACE_SLUG,
    }
    if project_id:
        env["AGENTPM_AGENT_ADMIN_PROJECT_ID"] = project_id
    command = ["docker", "compose", "-f", "docker-compose.yml", "exec", "-T", "api", "python", "manage.py", "shell"]
    result = subprocess.run(
        command,
        cwd=PLANE_DIR,
        input=_DJANGO_ADMIN_SNIPPET,
        text=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    json_line = ""
    for line in result.stdout.splitlines():
        if line.startswith("AGENTPM_AGENT_ADMIN_RESULT="):
            json_line = line.split("=", 1)[1]
    if not json_line:
        raise RuntimeError(f"Plane admin command did not return a result: {result.stdout}")
    return json.loads(json_line)


def _upsert_agent_env(agent_id: str, user_info: Mapping[str, Any], token: str) -> None:
    values = _read_agent_env_file(ENV_FILE)
    token_map = _load_json_mapping(values.get("PLANE_AGENT_TOKEN_MAP"), "PLANE_AGENT_TOKEN_MAP")
    user_map = _load_json_mapping(values.get("PLANE_AGENT_USER_MAP"), "PLANE_AGENT_USER_MAP")
    token_map[agent_id] = token
    user_map[agent_id] = dict(user_info)
    values["PLANE_AGENT_TOKEN_MAP"] = json.dumps(token_map, sort_keys=True)
    values["PLANE_AGENT_USER_MAP"] = json.dumps(user_map, sort_keys=True)
    values.setdefault("PLANE_MCP_AGENT_ID", "hekate")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"export {key}={shlex.quote(value)}" for key, value in sorted(values.items())]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def _read_agent_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("export "):
            continue
        for part in shlex.split(line)[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            values[key] = value
    return values


def _load_json_mapping(raw: str | None, name: str) -> dict[str, Any]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object")
    return parsed


def _print(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


_DJANGO_ADMIN_SNIPPET = r"""
import json
import os

from plane.db.models import APIToken, Project, ProjectMember, User, Workspace, WorkspaceMember

mode = os.environ["AGENTPM_AGENT_ADMIN_MODE"]
spec = json.loads(os.environ["AGENTPM_AGENT_ADMIN_SPEC"])
workspace = Workspace.objects.get(slug=os.environ.get("AGENTPM_AGENT_ADMIN_WORKSPACE_SLUG", "agentpm"))
project_id = os.environ.get("AGENTPM_AGENT_ADMIN_PROJECT_ID")

if mode == "approve_agent":
    user, _ = User.objects.get_or_create(
        email=spec["email"],
        defaults={
            "username": spec.get("username") or f"agent-{spec['agent_id']}",
            "display_name": spec["display_name"],
            "first_name": spec["display_name"],
            "last_name": "Agent",
            "is_active": True,
            "is_email_verified": True,
            "is_email_valid": True,
            "is_bot": True,
            "bot_type": "WORKSPACE_SEED",
        },
    )
    user.username = spec.get("username") or f"agent-{spec['agent_id']}"
    user.display_name = spec["display_name"]
    user.first_name = spec["display_name"]
    user.last_name = "Agent"
    user.is_active = True
    user.is_email_verified = True
    user.is_email_valid = True
    user.is_bot = True
    user.bot_type = "WORKSPACE_SEED"
    user.set_unusable_password()
    user.save()

    workspace_member, _ = WorkspaceMember.objects.get_or_create(
        workspace=workspace,
        member=user,
        defaults={"role": spec["workspace_role"], "is_active": True},
    )
    workspace_member.role = spec["workspace_role"]
    workspace_member.is_active = True
    workspace_member.save()

    if project_id:
        project = Project.objects.get(workspace=workspace, id=project_id)
        project_member, _ = ProjectMember.objects.get_or_create(
            workspace=workspace,
            project=project,
            member=user,
            defaults={"role": spec["project_role"], "is_active": True},
        )
        project_member.role = spec["project_role"]
        project_member.is_active = True
        project_member.save()

    token, _ = APIToken.objects.get_or_create(
        user=user,
        workspace=workspace,
        label=f"AgentPM {spec['agent_id']} MCP",
        is_service=True,
        defaults={
            "description": f"AgentPM MCP token for {spec['display_name']}",
            "user_type": 1,
            "is_active": True,
            "allowed_rate_limit": "1000/min",
        },
    )
    token.description = f"AgentPM MCP token for {spec['display_name']}"
    token.user_type = 1
    token.is_active = True
    token.allowed_rate_limit = "1000/min"
    token.save()
    result = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "workspace_role": spec["workspace_role"],
            "project_role": spec["project_role"],
            "role_name": spec["role_name"],
        },
        "token": token.token,
    }
elif mode == "add_to_project":
    project = Project.objects.get(workspace=workspace, id=project_id)
    project_member, _ = ProjectMember.objects.get_or_create(
        workspace=workspace,
        project=project,
        member_id=spec["member_id"],
        defaults={"role": spec["role"], "is_active": True},
    )
    project_member.role = spec["role"]
    project_member.is_active = True
    project_member.save()
    result = {"id": str(project_member.id), "member_id": str(project_member.member_id), "role": project_member.role}
else:
    raise ValueError(f"unknown mode: {mode}")

print("AGENTPM_AGENT_ADMIN_RESULT=" + json.dumps(result, sort_keys=True))
"""


if __name__ == "__main__":
    main()
