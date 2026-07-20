# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import os
import urllib.error
import urllib.request

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectAdminPermission
from plane.app.views.base import BaseAPIView


def _agentpm_request(method, path, payload=None):
    base_url = os.environ.get("AGENTPM_INTERNAL_URL", "http://agentpm:8080").rstrip("/")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    admin_token = os.environ.get("AGENTPM_ADMIN_TOKEN")
    if admin_token:
        headers["X-AgentPM-Admin-Token"] = admin_token
    request = urllib.request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # nosec B310 - fixed internal URL
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {"error": {"message": str(exc)}}
    except (urllib.error.URLError, TimeoutError) as exc:
        return status.HTTP_503_SERVICE_UNAVAILABLE, {
            "error": {"code": "AGENTPM_UNAVAILABLE", "message": f"AgentPM is unavailable: {exc}"}
        }


class AgentPolicyEndpoint(BaseAPIView):
    permission_classes = [ProjectAdminPermission]

    def get(self, request, slug, project_id):
        response_status, payload = _agentpm_request("GET", f"/policies/projects/{project_id}")
        return Response(payload, status=response_status)

    def post(self, request, slug, project_id):
        payload = dict(request.data)
        payload["published_by"] = str(request.user.id)
        response_status, response_payload = _agentpm_request(
            "POST", f"/policies/projects/{project_id}", payload
        )
        return Response(response_payload, status=response_status)


class AgentPolicyHistoryEndpoint(BaseAPIView):
    permission_classes = [ProjectAdminPermission]

    def get(self, request, slug, project_id):
        response_status, payload = _agentpm_request("GET", f"/policies/projects/{project_id}/history")
        return Response(payload, status=response_status)


class AgentPolicyRuntimeEndpoint(BaseAPIView):
    permission_classes = [ProjectAdminPermission]

    def get(self, request, slug, project_id):
        response_status, payload = _agentpm_request("GET", f"/runtime/projects/{project_id}")
        return Response(payload, status=response_status)


class AgentPolicyApprovalEndpoint(BaseAPIView):
    permission_classes = [ProjectAdminPermission]

    def post(self, request, slug, project_id, approval_id):
        payload = {
            "decision": request.data.get("decision"),
            "note": request.data.get("note"),
            "reviewer_id": str(request.user.id),
        }
        response_status, response_payload = _agentpm_request(
            "POST", f"/approvals/{approval_id}/decision", payload
        )
        return Response(response_payload, status=response_status)
