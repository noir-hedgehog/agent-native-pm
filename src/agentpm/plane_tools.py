from __future__ import annotations

import json
import os
import html
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List

from .agent_accounts import extract_assignee_ids


@dataclass
class PlaneToolConfig:
    base_url: str
    workspace_slug: str
    api_token: str | None = None
    api_key_header: str = "X-Api-Key"
    project_id: str | None = None
    status_field: str = "state"
    status_map: Dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> "PlaneToolConfig":
        status_map_raw = os.environ.get("PLANE_STATUS_MAP", "{}")
        try:
            status_map = json.loads(status_map_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("PLANE_STATUS_MAP must be valid JSON") from exc
        if not isinstance(status_map, dict):
            raise ValueError("PLANE_STATUS_MAP must be a JSON object")

        return cls(
            base_url=_required_env("PLANE_API_BASE_URL").rstrip("/"),
            workspace_slug=_required_env("PLANE_WORKSPACE_SLUG"),
            api_token=os.environ.get("PLANE_API_TOKEN"),
            api_key_header=os.environ.get("PLANE_API_KEY_HEADER", "X-Api-Key"),
            project_id=os.environ.get("PLANE_PROJECT_ID") or os.environ.get("REAL_PROJECT_ID"),
            status_field=os.environ.get("PLANE_STATUS_FIELD", "state"),
            status_map={str(key): str(value) for key, value in status_map.items()},
        )

    def with_api_token(self, api_token: str | None) -> "PlaneToolConfig":
        return replace(self, api_token=api_token)


class PlaneClient:
    def __init__(self, config: PlaneToolConfig) -> None:
        self.config = config
        self._state_names_by_id: Dict[str, str] | None = None

    def list_projects(self) -> Dict[str, Any]:
        return self._get(f"/api/v1/workspaces/{self.config.workspace_slug}/projects/")

    def create_project(
        self,
        *,
        name: str,
        identifier: str,
        description: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name, "identifier": identifier}
        if description:
            payload["description"] = description
        return self._post(f"/api/v1/workspaces/{self.config.workspace_slug}/projects/", payload)

    def add_project_member(self, project_id: str, member_id: str, role: int) -> Dict[str, Any]:
        return self._post(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{project_id}/members/",
            {"member": member_id, "role": role},
        )

    def list_states(self, project_id: str | None = None) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._get(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/states/"
        )

    def list_work_items(
        self,
        *,
        project_id: str | None = None,
        state: str | None = None,
        search: str | None = None,
    ) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        query = {}
        if state:
            query["state"] = self._map_status(state)
        if search:
            query["search"] = search
        return self._get(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/",
            query=query,
        )

    def get_work_item(self, work_item_id: str, *, project_id: str | None = None) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._get(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/{work_item_id}/"
        )

    def list_comments(self, work_item_id: str, *, project_id: str | None = None) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._get(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/{work_item_id}/comments/"
        )

    def add_comment(self, work_item_id: str, body: str, *, project_id: str | None = None) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._post(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/{work_item_id}/comments/",
            {
                "comment_html": body,
                "external_source": "agentpm-plane-tools",
            },
        )

    def create_work_item(
        self,
        *,
        name: str,
        assignee_id: str,
        project_id: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        state: str | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
    ) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        payload: Dict[str, Any] = {"name": name, "assignees": [assignee_id]}
        if description:
            payload["description_html"] = f"<p>{html.escape(description)}</p>"
        if priority:
            payload["priority"] = priority
        if state:
            payload["state"] = self._map_status(state)
        if external_source:
            payload["external_source"] = external_source
        if external_id:
            payload["external_id"] = external_id
        return self._post(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/",
            payload,
        )

    def update_work_item_status(
        self,
        work_item_id: str,
        status: str,
        *,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._patch(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/{work_item_id}/",
            {self.config.status_field: self._map_status(status)},
        )

    def assign_work_item(
        self,
        work_item_id: str,
        assignee_id: str,
        *,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        resolved_project_id = self._project_id(project_id)
        return self._patch(
            f"/api/v1/workspaces/{self.config.workspace_slug}/projects/{resolved_project_id}/work-items/{work_item_id}/",
            {"assignee_ids": [assignee_id]},
        )

    def summarize_work_item(self, work_item_id: str, *, project_id: str | None = None) -> Dict[str, Any]:
        item = self.get_work_item(work_item_id, project_id=project_id)
        comments = self.list_comments(work_item_id, project_id=project_id)
        comment_rows = sorted(
            _rows(comments),
            key=lambda comment: comment.get("created_at") or comment.get("createdAt") or "",
            reverse=True,
        )
        return {
            "work_item": self.compact_work_item(item),
            "recent_comments": [_compact_comment(comment) for comment in comment_rows[:5]],
        }

    def compact_work_items(self, payload: Dict[str, Any], *, limit: int = 50) -> List[Dict[str, Any]]:
        return [self.compact_work_item(row) for row in _rows(payload)[:limit]]

    def compact_work_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return _compact_work_item(item, state_names_by_id=self._state_name_lookup())

    def _map_status(self, status: str) -> str:
        return (self.config.status_map or {}).get(status, status)

    def _project_id(self, project_id: str | None) -> str:
        resolved = project_id or self.config.project_id
        if not resolved:
            raise ValueError("project_id is required; pass --project-id or set PLANE_PROJECT_ID/REAL_PROJECT_ID")
        return resolved

    def _get(self, path: str, *, query: Dict[str, str] | None = None) -> Dict[str, Any]:
        if query:
            path = f"{path}?{urllib.parse.urlencode(query)}"
        return self._request("GET", path)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, payload)

    def _patch(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", path, payload)

    def _request(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if self.config.api_token:
            headers[self.config.api_key_header] = self.config.api_token

        req = urllib.request.Request(
            url=f"{self.config.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req) as response:  # nosec B310 - configured Plane URL
            data = response.read().decode("utf-8")
            if not data:
                return {}
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
            return {"results": parsed}

    def _state_name_lookup(self) -> Dict[str, str]:
        if self._state_names_by_id is not None:
            return self._state_names_by_id
        try:
            states = self.list_states()
        except Exception:
            self._state_names_by_id = {}
            return self._state_names_by_id
        self._state_names_by_id = {
            str(row["id"]): str(row["name"])
            for row in _rows(states)
            if row.get("id") and row.get("name")
        }
        return self._state_names_by_id


def list_tool_rows(payload: Dict[str, Any], *, limit: int = 50) -> List[Dict[str, Any]]:
    return [_compact_work_item(row) for row in _rows(payload)[:limit]]


def _rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("results", "data", "items"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return payload
    return []


def _compact_work_item(item: Dict[str, Any], *, state_names_by_id: Dict[str, str] | None = None) -> Dict[str, Any]:
    state = item.get("state")
    if isinstance(state, dict):
        state_value = state.get("name") or state.get("id")
    else:
        state_value = (state_names_by_id or {}).get(str(state), state)
    return _without_empty(
        {
            "id": item.get("id"),
            "name": item.get("name") or item.get("title"),
            "sequence_id": item.get("sequence_id") or item.get("sequenceId"),
            "state": state_value,
            "priority": item.get("priority"),
            "updated_at": item.get("updated_at") or item.get("updatedAt"),
            "description": item.get("description_stripped") or item.get("description_text"),
            "assignee_ids": sorted(extract_assignee_ids(item)),
        }
    )


def _compact_comment(comment: Dict[str, Any]) -> Dict[str, Any]:
    return _without_empty(
        {
            "id": comment.get("id"),
            "body": comment.get("comment_stripped")
            or comment.get("comment_html")
            or comment.get("body")
            or comment.get("comment"),
            "created_at": comment.get("created_at") or comment.get("createdAt"),
            "updated_at": comment.get("updated_at") or comment.get("updatedAt"),
        }
    )


def _without_empty(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, "")}


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value
