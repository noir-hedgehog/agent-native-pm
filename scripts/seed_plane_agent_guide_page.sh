#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOC_PATH="${MESH_AGENT_GUIDE_DOC:-${AGENTPM_AGENT_GUIDE_DOC:-docs/agent-plane-mcp-guide.md}}"
PAGE_TITLE="${MESH_AGENT_GUIDE_PAGE_TITLE:-${AGENTPM_AGENT_GUIDE_PAGE_TITLE:-Mesh Agent Guide: Console + MCP}}"
EXTERNAL_SOURCE="mesh"
EXTERNAL_ID="mesh-console-mcp-guide"
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

if [ ! -f "$DOC_PATH" ]; then
  echo "Guide source not found: $DOC_PATH" >&2
  exit 1
fi

API_CONTAINER="$("${DOCKER[@]}" ps --filter 'name=^/api$' --format '{{.ID}}' | head -1)"
if [ -z "$API_CONTAINER" ]; then
  echo "Plane api container is not running. Start it with ./scripts/plane_service.sh backend" >&2
  exit 1
fi

PLANE_WORKSPACE_SLUG="${PLANE_WORKSPACE_SLUG:-agentpm}"
REAL_PROJECT_ID="${MESH_PROJECT_ID:-${REAL_PROJECT_ID:-}}"
if [ -z "$REAL_PROJECT_ID" ]; then
  REAL_PROJECT_ID="$("${DOCKER[@]}" exec -e PLANE_WORKSPACE_SLUG="$PLANE_WORKSPACE_SLUG" "$API_CONTAINER" python manage.py shell -c 'import os; from plane.db.models import Project; project = Project.objects.filter(workspace__slug=os.environ["PLANE_WORKSPACE_SLUG"], deleted_at__isnull=True).order_by("created_at").first(); print(project.id if project else "")' | tail -1)"
fi
if [ -z "$REAL_PROJECT_ID" ]; then
  echo "No Plane project found in workspace: $PLANE_WORKSPACE_SLUG" >&2
  exit 1
fi

CONTAINER_DOC="/tmp/agent-plane-mcp-guide.md"
"${DOCKER[@]}" cp "$DOC_PATH" "$API_CONTAINER:$CONTAINER_DOC"

"${DOCKER[@]}" exec -i \
  -e PLANE_WORKSPACE_SLUG="$PLANE_WORKSPACE_SLUG" \
  -e REAL_PROJECT_ID="$REAL_PROJECT_ID" \
  -e GUIDE_DOC_PATH="$CONTAINER_DOC" \
  -e GUIDE_PAGE_TITLE="$PAGE_TITLE" \
  -e GUIDE_EXTERNAL_SOURCE="$EXTERNAL_SOURCE" \
  -e GUIDE_EXTERNAL_ID="$EXTERNAL_ID" \
  "$API_CONTAINER" python manage.py shell <<'PY'
import html
import os
from pathlib import Path

from django.utils import timezone
from plane.db.models import Page, Project, ProjectMember, ProjectPage, WorkspaceMember


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output = []
    list_open = False
    code_open = False
    code_lines = []

    def close_list():
        nonlocal list_open
        if list_open:
            output.append("</ul>")
            list_open = False

    def close_code():
        nonlocal code_open, code_lines
        if code_open:
            output.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
            code_open = False
            code_lines = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            if code_open:
                close_code()
            else:
                close_list()
                code_open = True
                code_lines = []
            continue
        if code_open:
            code_lines.append(line)
            continue
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            output.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_list()
            output.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_list()
            output.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            if not list_open:
                output.append("<ul>")
                list_open = True
            output.append(f"<li>{html.escape(line[2:].strip())}</li>")
        else:
            close_list()
            output.append(f"<p>{html.escape(line)}</p>")
    close_code()
    close_list()
    return "\n".join(output) or "<p></p>"


workspace_slug = os.environ["PLANE_WORKSPACE_SLUG"]
project_id = os.environ["REAL_PROJECT_ID"]
doc_path = Path(os.environ["GUIDE_DOC_PATH"])
title = os.environ["GUIDE_PAGE_TITLE"]
external_source = os.environ["GUIDE_EXTERNAL_SOURCE"]
external_id = os.environ["GUIDE_EXTERNAL_ID"]

project = Project.objects.select_related("workspace", "project_lead").get(id=project_id, workspace__slug=workspace_slug)
workspace = project.workspace
human_admin = (
    WorkspaceMember.objects.filter(
        workspace=workspace,
        is_active=True,
        role__gte=20,
        member__is_bot=False,
    )
    .select_related("member")
    .first()
)
owner = human_admin.member if human_admin else (project.project_lead or workspace.owner)
if owner is None:
    admin_member = (
        WorkspaceMember.objects.filter(workspace=workspace, is_active=True, role__gte=20)
        .select_related("member")
        .first()
    )
    owner = admin_member.member if admin_member else None
if owner is None:
    project_member = ProjectMember.objects.filter(project=project, is_active=True).select_related("member").first()
    owner = project_member.member
if owner is None:
    raise RuntimeError("Could not resolve an owner for the guide page")

markdown = doc_path.read_text()
description_html = markdown_to_html(markdown)

page = (
    Page.objects.filter(workspace=workspace, external_source=external_source, external_id=external_id).first()
    or Page.objects.filter(workspace=workspace, external_source="agentpm", external_id="agent-plane-mcp-guide").first()
    or Page.objects.filter(workspace=workspace, projects=project, name=title).first()
)

created = page is None
if created:
    page = Page(
        workspace=workspace,
        name=title,
        access=Page.PUBLIC_ACCESS,
        description_json={},
        description_html=description_html,
        source_format="markdown",
        source_text=markdown,
        owned_by=owner,
        created_by=owner,
        updated_by=owner,
        external_source=external_source,
        external_id=external_id,
    )
else:
    page.name = title
    page.access = Page.PUBLIC_ACCESS
    page.description_html = description_html
    page.description_json = {}
    page.source_format = "markdown"
    page.source_text = markdown
    page.updated_by = owner
    page.external_source = external_source
    page.external_id = external_id
    page.updated_at = timezone.now()

page.save(created_by_id=owner.id, disable_auto_set_user=True)
ProjectPage.objects.get_or_create(
    workspace=workspace,
    project=project,
    page=page,
    defaults={"created_by": owner, "updated_by": owner},
)

print(f"PAGE_STATUS={'created' if created else 'updated'}")
print(f"PAGE_ID={page.id}")
print(f"PAGE_TITLE={page.name}")
print(f"PROJECT_ID={project.id}")
PY
