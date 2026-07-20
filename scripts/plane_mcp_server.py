#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable, Dict
import urllib.error
import urllib.request

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from agentpm.agent_accounts import AgentAccount, AgentAccountRegistry, extract_assignee_ids
from agentpm.agent_applications import AgentApplicationStore
from agentpm.plane_tools import PlaneClient, PlaneToolConfig


PROTOCOL_VERSION = "2024-11-05"


def main() -> None:
    server = PlaneMcpServer()
    server.serve()


class PlaneMcpServer:
    def __init__(self) -> None:
        self.config = PlaneToolConfig.from_env()
        self.agent_registry = AgentAccountRegistry.from_env()
        self.application_store = AgentApplicationStore()
        self.locked_agent_id = os.environ.get("PLANE_MCP_LOCKED_AGENT_ID")
        self.agentpm_base_url = os.environ.get("AGENTPM_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        self.tools: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "plane_request_agent_registration": self._request_agent_registration,
            "plane_list_projects": self._list_projects,
            "plane_list_work_items": self._list_work_items,
            "plane_get_work_item": self._get_work_item,
            "plane_summarize_work_item": self._summarize_work_item,
            "plane_add_comment": self._add_comment,
            "plane_update_status": self._update_status,
            "plane_assign_work_item": self._assign_work_item,
            "plane_create_project": self._create_project,
            "plane_create_work_item": self._create_work_item,
            "plane_list_agent_accounts": self._list_agent_accounts,
            "plane_list_states": self._list_states,
            "plane_get_project_policy": self._get_project_policy,
            "plane_publish_project_policy": self._publish_project_policy,
        }

    def serve(self) -> None:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                response = self.handle(request)
            except Exception as exc:  # Keep stdio MCP alive and report JSON-RPC errors.
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(exc), "data": traceback.format_exc(limit=5)},
                }
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}

        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "agentpm-plane", "version": "0.1.0"},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return self._result(request_id, {"tools": self._tool_descriptors()})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in self.tools:
                return self._error(request_id, -32602, f"unknown tool: {name}")
            try:
                result = self.tools[name](arguments)
            except Exception as exc:
                return self._error(request_id, -32000, str(exc))
            return self._result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ],
                    "isError": False,
                },
            )
        if method in {"resources/list", "prompts/list"}:
            key = "resources" if method == "resources/list" else "prompts"
            return self._result(request_id, {key: []})
        return self._error(request_id, -32601, f"method not found: {method}")

    def _list_projects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "read")
        return client.list_projects()

    def _request_agent_registration(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self.application_store.request_registration(
            agent_id=_required_arg(args, "agent_id"),
            display_name=_required_arg(args, "display_name"),
            email=args.get("email"),
            requested_role=str(args.get("requested_role") or "member"),
            reason=str(args.get("reason") or ""),
            project_id=args.get("project_id"),
            source="mcp_bootstrap",
        )
        return {
            **result,
            "message": "registration request recorded; a human Plane admin must approve it before token access",
        }

    def _list_states(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "read")
        return client.list_states(project_id=args.get("project_id"))

    def _list_work_items(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "read")
        limit = int(args.get("limit") or 50)
        payload = client.list_work_items(
            project_id=args.get("project_id"),
            state=args.get("state"),
            search=args.get("search"),
        )
        return {"work_items": client.compact_work_items(payload, limit=limit)}

    def _get_work_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "read")
        return client.get_work_item(_required_arg(args, "work_item_id"), project_id=args.get("project_id"))

    def _summarize_work_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "read")
        return client.summarize_work_item(_required_arg(args, "work_item_id"), project_id=args.get("project_id"))

    def _add_comment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "comment")
        return client.add_comment(
            _required_arg(args, "work_item_id"),
            _required_arg(args, "body"),
            project_id=args.get("project_id"),
        )

    def _update_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, account = self._client_for(args, "update_status")
        work_item_id = _required_arg(args, "work_item_id")
        self._require_status_update_scope(client, account, work_item_id, project_id=args.get("project_id"))
        return client.update_work_item_status(
            work_item_id,
            _required_arg(args, "status"),
            project_id=args.get("project_id"),
        )

    def _assign_work_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "assign")
        target = self.agent_registry.get(_required_arg(args, "target_agent_id"))
        if target.project_role < 15:
            raise PermissionError(f"target_agent_id={target.agent_id} cannot be assigned Plane work items as a Guest")
        if not target.plane_user_id:
            raise ValueError(f"target_agent_id={target.agent_id} is missing plane_user_id")
        return client.assign_work_item(
            _required_arg(args, "work_item_id"),
            target.plane_user_id,
            project_id=args.get("project_id"),
        )

    def _create_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "create_project")
        project = client.create_project(
            name=_required_arg(args, "name"),
            identifier=_required_arg(args, "identifier"),
            description=args.get("description"),
        )
        project_id = str(project.get("id") or "")
        added_members = []
        for agent_id in args.get("member_agent_ids") or []:
            account = self.agent_registry.get(str(agent_id))
            if not account.plane_user_id:
                raise ValueError(f"agent_id={account.agent_id} is missing plane_user_id")
            if project_id:
                added_members.append(client.add_project_member(project_id, account.plane_user_id, account.project_role))
        return {"project": project, "added_members": added_members}

    def _create_work_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        client, _ = self._client_for(args, "create_work_item")
        target = self.agent_registry.get(_required_arg(args, "target_agent_id"))
        if target.project_role < 15:
            raise PermissionError(f"target_agent_id={target.agent_id} cannot be assigned Plane work items as a Guest")
        if not target.plane_user_id:
            raise ValueError(f"target_agent_id={target.agent_id} is missing plane_user_id")
        return client.create_work_item(
            name=_required_arg(args, "name"),
            assignee_id=target.plane_user_id,
            project_id=_required_arg(args, "project_id"),
            description=args.get("description"),
            priority=args.get("priority"),
            state=args.get("state"),
            external_source=args.get("external_source"),
            external_id=args.get("external_id"),
        )

    def _list_agent_accounts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._client_for(args, "read")
        return {
            "default_agent_id": self.agent_registry.default_agent_id,
            "locked_agent_id": self.locked_agent_id,
            "agents": self.agent_registry.public_accounts(),
            "applications": [application.public_dict for application in self.application_store.list()],
        }

    def _get_project_policy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._client_for(args, "read")
        project_id = _required_arg(args, "project_id")
        return _agentpm_request("GET", f"{self.agentpm_base_url}/policies/projects/{project_id}")

    def _publish_project_policy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        _, account = self._client_for(args, "read")
        if account.project_role < 20:
            raise PermissionError(f"agent_id={account.agent_id} cannot publish project policy")
        project_id = _required_arg(args, "project_id")
        policy = args.get("policy")
        if not isinstance(policy, dict):
            raise ValueError("policy is required")
        return _agentpm_request("POST", f"{self.agentpm_base_url}/policies/projects/{project_id}", policy)

    def _client_for(self, args: Dict[str, Any], capability: str) -> tuple[PlaneClient, AgentAccount]:
        requested_agent_id = args.get("agent_id")
        if self.locked_agent_id and requested_agent_id and requested_agent_id != self.locked_agent_id:
            raise PermissionError(
                f"this MCP server is locked to agent_id={self.locked_agent_id}; requested agent_id={requested_agent_id}"
            )
        account = self.agent_registry.get(self.locked_agent_id or requested_agent_id)
        self.agent_registry.require_capability(account, capability)
        if not account.token:
            raise ValueError(f"missing Plane API token for agent_id={account.agent_id}; run scripts/seed_plane_agents.sh")
        return PlaneClient(self.config.with_api_token(account.token)), account

    def _require_status_update_scope(
        self,
        client: PlaneClient,
        account: AgentAccount,
        work_item_id: str,
        *,
        project_id: str | None = None,
    ) -> None:
        if account.agent_id == "hekate":
            return
        if not account.plane_user_id:
            raise PermissionError(f"agent_id={account.agent_id} cannot update status without a plane_user_id")

        item = client.get_work_item(work_item_id, project_id=project_id)
        assignee_ids = extract_assignee_ids(item)
        if account.plane_user_id not in assignee_ids:
            raise PermissionError(
                f"agent_id={account.agent_id} can only update work items assigned to its Plane user"
            )

    def _tool_descriptors(self) -> list[Dict[str, Any]]:
        return [
            {
                "name": "plane_request_agent_registration",
                "description": "Submit a bootstrap registration or project-join request for an unknown Agent. Does not grant token access.",
                "inputSchema": _schema(
                    {
                        "agent_id": {"type": "string"},
                        "display_name": {"type": "string"},
                        "email": {"type": "string"},
                        "requested_role": {"type": "string", "enum": ["admin", "member", "guest"]},
                        "reason": {"type": "string"},
                        "project_id": {"type": "string"},
                    },
                    ["agent_id", "display_name"],
                ),
            },
            {
                "name": "plane_list_projects",
                "description": "List Plane projects in the configured workspace.",
                "inputSchema": _schema(_agent_properties()),
            },
            {
                "name": "plane_list_states",
                "description": "List states for a Plane project.",
                "inputSchema": _schema(_agent_properties({"project_id": {"type": "string"}})),
            },
            {
                "name": "plane_list_work_items",
                "description": "List Plane work items. Supports optional state/search filters.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "project_id": {"type": "string"},
                            "state": {"type": "string"},
                            "search": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        }
                    )
                ),
            },
            {
                "name": "plane_get_work_item",
                "description": "Get one Plane work item by id.",
                "inputSchema": _schema(
                    _agent_properties({"work_item_id": {"type": "string"}, "project_id": {"type": "string"}}),
                    ["work_item_id"],
                ),
            },
            {
                "name": "plane_summarize_work_item",
                "description": "Get a compact work item summary plus recent comments.",
                "inputSchema": _schema(
                    _agent_properties({"work_item_id": {"type": "string"}, "project_id": {"type": "string"}}),
                    ["work_item_id"],
                ),
            },
            {
                "name": "plane_add_comment",
                "description": "Add a comment to a Plane work item.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "work_item_id": {"type": "string"},
                            "body": {"type": "string"},
                            "project_id": {"type": "string"},
                        }
                    ),
                    ["work_item_id", "body"],
                ),
            },
            {
                "name": "plane_update_status",
                "description": "Update a Plane work item status/state. Friendly statuses are mapped with PLANE_STATUS_MAP.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "work_item_id": {"type": "string"},
                            "status": {"type": "string"},
                            "project_id": {"type": "string"},
                        }
                    ),
                    ["work_item_id", "status"],
                ),
            },
            {
                "name": "plane_assign_work_item",
                "description": "Assign a Plane work item to an Agent Plane user. Hekate only.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "work_item_id": {"type": "string"},
                            "target_agent_id": {"type": "string"},
                            "project_id": {"type": "string"},
                        }
                    ),
                    ["work_item_id", "target_agent_id"],
                ),
            },
            {
                "name": "plane_create_project",
                "description": "Create a Plane project and optionally add Agent members. Admin agents only.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "name": {"type": "string"},
                            "identifier": {"type": "string"},
                            "description": {"type": "string"},
                            "member_agent_ids": {"type": "array", "items": {"type": "string"}},
                        }
                    ),
                    ["name", "identifier"],
                ),
            },
            {
                "name": "plane_create_work_item",
                "description": "Create a Plane work item and explicitly assign it to an executable Agent.",
                "inputSchema": _schema(
                    _agent_properties(
                        {
                            "project_id": {"type": "string"},
                            "name": {"type": "string"},
                            "target_agent_id": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "string"},
                            "state": {"type": "string"},
                            "external_source": {"type": "string"},
                            "external_id": {"type": "string"},
                        }
                    ),
                    ["project_id", "name", "target_agent_id"],
                ),
            },
            {
                "name": "plane_list_agent_accounts",
                "description": "List configured Agent Plane users, roles, and capabilities. Tokens are never returned.",
                "inputSchema": _schema(_agent_properties()),
            },
            {
                "name": "plane_get_project_policy",
                "description": "Get the latest AgentPM project policy for a Plane project.",
                "inputSchema": _schema(_agent_properties({"project_id": {"type": "string"}}), ["project_id"]),
            },
            {
                "name": "plane_publish_project_policy",
                "description": "Publish a new AgentPM project policy version. Admin agents only.",
                "inputSchema": _schema(
                    _agent_properties({"project_id": {"type": "string"}, "policy": {"type": "object"}}),
                    ["project_id", "policy"],
                ),
            },
        ]

    @staticmethod
    def _result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _schema(properties: Dict[str, Any], required: list[str] | None = None) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _agent_properties(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    properties = {
        "agent_id": {
            "type": "string",
            "description": "Agent identity used for Plane API token selection and MCP policy enforcement.",
        }
    }
    if extra:
        properties.update(extra)
    return properties


def _required_arg(args: Dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return str(value)


def _agentpm_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:  # nosec B310 - AgentPM URL is local/configured by env
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        if body:
            raise RuntimeError(body)
        raise
    return json.loads(body) if body else {}


if __name__ == "__main__":
    main()
