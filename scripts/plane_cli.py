#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from agentpm.agent_accounts import AgentAccountRegistry, extract_assignee_ids
from agentpm.agent_applications import AgentApplicationStore
from agentpm.plane_tools import PlaneClient, PlaneToolConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Plane CLI for AgentRedmine/OpenClaw workflows")
    sub = parser.add_subparsers(dest="command", required=True)

    agents = sub.add_parser("agents", help="List configured Agent Plane accounts")
    _add_agent_arg(agents)

    request_agent = sub.add_parser("request-agent-registration", help="Request Agent registration or project access")
    request_agent.add_argument("agent_id")
    request_agent.add_argument("display_name")
    request_agent.add_argument("--email")
    request_agent.add_argument("--requested-role", choices=["admin", "member", "guest"], default="member")
    request_agent.add_argument("--reason", default="")
    request_agent.add_argument("--project-id")

    projects = sub.add_parser("projects", help="List Plane projects")
    _add_agent_arg(projects)

    states = sub.add_parser("states", help="List project states")
    states.add_argument("--project-id")
    _add_agent_arg(states)

    items = sub.add_parser("work-items", help="List Plane work items")
    items.add_argument("--project-id")
    items.add_argument("--state")
    items.add_argument("--search")
    items.add_argument("--limit", type=int, default=50)
    _add_agent_arg(items)

    item = sub.add_parser("work-item", help="Get one Plane work item")
    item.add_argument("work_item_id")
    item.add_argument("--project-id")
    _add_agent_arg(item)

    comments = sub.add_parser("comments", help="List comments for one work item")
    comments.add_argument("work_item_id")
    comments.add_argument("--project-id")
    _add_agent_arg(comments)

    comment = sub.add_parser("comment", help="Add a comment to one work item")
    comment.add_argument("work_item_id")
    comment.add_argument("body")
    comment.add_argument("--project-id")
    _add_agent_arg(comment)

    status = sub.add_parser("status", help="Update one work item status/state")
    status.add_argument("work_item_id")
    status.add_argument("status")
    status.add_argument("--project-id")
    _add_agent_arg(status)

    assign = sub.add_parser("assign", help="Assign one work item to an Agent Plane user")
    assign.add_argument("work_item_id")
    assign.add_argument("target_agent_id")
    assign.add_argument("--project-id")
    _add_agent_arg(assign)

    summary = sub.add_parser("summary", help="Summarize one work item with recent comments")
    summary.add_argument("work_item_id")
    summary.add_argument("--project-id")
    _add_agent_arg(summary)

    create_project = sub.add_parser("create-project", help="Create a Plane project as an Agent")
    create_project.add_argument("name")
    create_project.add_argument("identifier")
    create_project.add_argument("--description")
    create_project.add_argument("--member-agent-id", action="append", default=[])
    _add_agent_arg(create_project)

    create_item = sub.add_parser("create-work-item", help="Create a Plane work item and assign it to an Agent")
    create_item.add_argument("project_id")
    create_item.add_argument("name")
    create_item.add_argument("target_agent_id")
    create_item.add_argument("--description")
    create_item.add_argument("--priority")
    create_item.add_argument("--state")
    create_item.add_argument("--external-source")
    create_item.add_argument("--external-id")
    _add_agent_arg(create_item)

    args = parser.parse_args()
    registry = AgentAccountRegistry.from_env()

    if args.command == "request-agent-registration":
        result = AgentApplicationStore().request_registration(
            agent_id=args.agent_id,
            display_name=args.display_name,
            email=args.email,
            requested_role=args.requested_role,
            reason=args.reason,
            project_id=args.project_id,
            source="cli_bootstrap",
        )
        result["message"] = "registration request recorded; a human Plane admin must approve it before token access"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if args.command == "agents":
        if args.agent_id:
            _client_for_args(PlaneToolConfig.from_env(), registry, args)
        result = {
            "default_agent_id": registry.default_agent_id,
            "agents": registry.public_accounts(),
            "applications": [application.public_dict for application in AgentApplicationStore().list()],
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    config = PlaneToolConfig.from_env()
    client = _client_for_args(config, registry, args)

    if args.command == "projects":
        result = client.list_projects()
    elif args.command == "states":
        result = client.list_states(project_id=args.project_id)
    elif args.command == "work-items":
        payload = client.list_work_items(project_id=args.project_id, state=args.state, search=args.search)
        result = {"work_items": client.compact_work_items(payload, limit=args.limit)}
    elif args.command == "work-item":
        result = client.get_work_item(args.work_item_id, project_id=args.project_id)
    elif args.command == "comments":
        result = client.list_comments(args.work_item_id, project_id=args.project_id)
    elif args.command == "comment":
        if args.agent_id:
            registry.require_capability(registry.get(args.agent_id), "comment")
        result = client.add_comment(args.work_item_id, args.body, project_id=args.project_id)
    elif args.command == "status":
        if args.agent_id:
            account = registry.get(args.agent_id)
            registry.require_capability(account, "update_status")
            if account.agent_id != "hekate":
                if not account.plane_user_id:
                    raise PermissionError(f"agent_id={account.agent_id} cannot update status without a plane_user_id")
                item_payload = client.get_work_item(args.work_item_id, project_id=args.project_id)
                if account.plane_user_id not in extract_assignee_ids(item_payload):
                    raise PermissionError(
                        f"agent_id={account.agent_id} can only update work items assigned to its Plane user"
                    )
        result = client.update_work_item_status(args.work_item_id, args.status, project_id=args.project_id)
    elif args.command == "assign":
        account = registry.get(args.agent_id)
        registry.require_capability(account, "assign")
        target = registry.get(args.target_agent_id)
        if target.project_role < 15:
            raise PermissionError(f"target_agent_id={target.agent_id} cannot be assigned Plane work items as a Guest")
        if not target.plane_user_id:
            raise ValueError(f"target_agent_id={target.agent_id} is missing plane_user_id")
        result = client.assign_work_item(args.work_item_id, target.plane_user_id, project_id=args.project_id)
    elif args.command == "summary":
        result = client.summarize_work_item(args.work_item_id, project_id=args.project_id)
    elif args.command == "create-project":
        account = registry.get(args.agent_id)
        registry.require_capability(account, "create_project")
        project = client.create_project(name=args.name, identifier=args.identifier, description=args.description)
        added_members = []
        project_id = project.get("id")
        for agent_id in args.member_agent_id:
            target = registry.get(agent_id)
            if not target.plane_user_id:
                raise ValueError(f"agent_id={target.agent_id} is missing plane_user_id")
            added_members.append(client.add_project_member(str(project_id), target.plane_user_id, target.project_role))
        result = {"project": project, "added_members": added_members}
    elif args.command == "create-work-item":
        account = registry.get(args.agent_id)
        registry.require_capability(account, "create_work_item")
        target = registry.get(args.target_agent_id)
        if target.project_role < 15:
            raise PermissionError(f"target_agent_id={target.agent_id} cannot be assigned Plane work items as a Guest")
        if not target.plane_user_id:
            raise ValueError(f"target_agent_id={target.agent_id} is missing plane_user_id")
        result = client.create_work_item(
            name=args.name,
            assignee_id=target.plane_user_id,
            project_id=args.project_id,
            description=args.description,
            priority=args.priority,
            state=args.state,
            external_source=args.external_source,
            external_id=args.external_id,
        )
    else:
        raise AssertionError(args.command)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _add_agent_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent-id", help="Use an Agent Plane token")


def _client_for_args(config: PlaneToolConfig, registry: AgentAccountRegistry, args) -> PlaneClient:
    agent_id = getattr(args, "agent_id", None)
    if not agent_id and getattr(args, "command", None) == "assign":
        agent_id = registry.default_agent_id
    if not agent_id and getattr(args, "command", None) in {"create-project", "create-work-item"}:
        agent_id = registry.default_agent_id
    if not agent_id:
        return PlaneClient(config)
    account = registry.get(agent_id)
    registry.require_capability(account, "read")
    if not account.token:
        raise ValueError(f"missing Plane API token for agent_id={account.agent_id}; run scripts/seed_plane_agents.sh")
    return PlaneClient(config.with_api_token(account.token))


if __name__ == "__main__":
    main()
