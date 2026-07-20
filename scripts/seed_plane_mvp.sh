#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANE_DIR="${PLANE_DIR:-$ROOT_DIR/plane}"

if [ ! -d "$PLANE_DIR" ]; then
  echo "Plane checkout not found at $PLANE_DIR" >&2
  exit 1
fi

cd "$PLANE_DIR"

if [ "$(docker inspect -f '{{.State.Running}}' api 2>/dev/null || true)" = "true" ]; then
  API_EXEC=(docker exec -i api)
else
  DOCKER=(docker)
  if ! docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
  fi
  API_EXEC=("${DOCKER[@]}" compose -f docker-compose.yml exec -T api)
fi

"${API_EXEC[@]}" python manage.py shell <<'PY'
from plane.db.models import (
    APIToken,
    Issue,
    Project,
    ProjectMember,
    State,
    StateGroup,
    User,
    Workspace,
    WorkspaceMember,
)

email = "agentpm.local@example.com"
password = "AgentPM-local-123!"
user, user_created = User.objects.get_or_create(
    email=email,
    defaults={
        "username": "agentpm-local",
        "display_name": "AgentPM Local",
        "first_name": "AgentPM",
        "last_name": "Local",
        "is_active": True,
        "is_email_verified": True,
    },
)
user.username = "agentpm-local"
user.display_name = "AgentPM Local"
user.first_name = "AgentPM"
user.last_name = "Local"
user.is_active = True
user.is_email_verified = True
user.set_password(password)
user.save()

workspace, _ = Workspace.objects.get_or_create(
    slug="agentpm",
    defaults={
        "name": "AgentPM",
        "owner": user,
    },
)
workspace.name = "AgentPM"
workspace.owner = user
workspace.save()
WorkspaceMember.objects.get_or_create(
    workspace=workspace,
    member=user,
    defaults={"role": 20, "is_active": True},
)

project, _ = Project.objects.get_or_create(
    workspace=workspace,
    identifier="AGPM",
    defaults={
        "name": "AgentPM MVP",
        "description": "Local AgentPM MVP verification project",
        "network": 2,
        "project_lead": user,
    },
)
project.name = "AgentPM MVP"
project.description = "Local AgentPM MVP verification project"
project.network = 2
project.project_lead = user
project.save()
ProjectMember.objects.get_or_create(
    workspace=workspace,
    project=project,
    member=user,
    defaults={"role": 20, "is_active": True},
)

state_specs = [
    ("Backlog", "#60646C", StateGroup.BACKLOG.value, True, 15000),
    ("Todo", "#60646C", StateGroup.UNSTARTED.value, False, 25000),
    ("In Progress", "#F59E0B", StateGroup.STARTED.value, False, 35000),
    ("Awaiting Review", "#3B82F6", StateGroup.STARTED.value, False, 40000),
    ("Done", "#46A758", StateGroup.COMPLETED.value, False, 45000),
    ("Failed", "#9AA4BC", StateGroup.CANCELLED.value, False, 55000),
]
states = {}
for name, color, group, is_default, sequence in state_specs:
    state, _ = State.all_state_objects.get_or_create(
        project=project,
        workspace=workspace,
        name=name,
        defaults={
            "color": color,
            "group": group,
            "default": is_default,
            "sequence": sequence,
        },
    )
    changed = False
    if is_default and not state.default:
        state.default = True
        changed = True
    if changed:
        state.save()
    states[name] = state

if project.default_state_id != states["Backlog"].id:
    project.default_state = states["Backlog"]
    project.save()

issue, _ = Issue.objects.get_or_create(
    project=project,
    workspace=workspace,
    external_source="agentpm",
    external_id="agentpm-local-mvp",
    defaults={
        "name": "AgentPM local MVP smoke",
        "description_html": "<p>Created by AgentPM local MVP seed.</p>",
        "description_stripped": "Created by AgentPM local MVP seed.",
        "state": states["Todo"],
        "priority": "medium",
    },
)
issue.name = "AgentPM local MVP smoke"
issue.description_html = "<p>Created by AgentPM local MVP seed.</p>"
issue.description_stripped = "Created by AgentPM local MVP seed."
issue.priority = "medium"
if issue.state_id is None:
    issue.state = states["Todo"]
issue.save()

backlog_specs = [
    (
        "agentpm-v1-01-assignment-webhook-ingestion",
        "Assignment Webhook Ingestion + Idempotency",
        states["Done"],
        "high",
        "Receive Plane assignment events, verify signatures, persist dedupe keys, and emit normalized internal trigger events.",
        "Implemented and covered by assignment webhook tests plus local smoke verification.",
    ),
    (
        "agentpm-v1-02-task-session-agent-run-persistence",
        "TaskSession + AgentRun Persistence Model",
        states["Done"],
        "high",
        "Add repositories for task sessions, agent runs, handoff contracts, approvals, and audit events.",
        "Implemented in the store layer with in-memory and SQLite-backed paths covered by tests.",
    ),
    (
        "agentpm-v1-03-openclaw-adapter",
        "OpenClaw Adapter V1 (Start/Status/Cancel/Stream)",
        states["Done"],
        "high",
        "Provider adapter implementing normalized run lifecycle on top of OpenClaw-compatible session APIs.",
        "Verified through the local OpenClaw connector smoke path and mock provider.",
    ),
    (
        "agentpm-v1-04-plane-writeback-adapter",
        "Plane Write-back Adapter V1",
        states["Done"],
        "high",
        "Write stage comments and status updates back to Plane work items.",
        "Verified against the local Plane API with seeded workspace, API token, comments, and state mapping.",
    ),
    (
        "agentpm-v1-05-single-agent-e2e",
        "Single-Agent Vertical Slice (E2E)",
        states["Done"],
        "high",
        "End-to-end flow from assignment to one agent run completion with audit trail and Plane write-back.",
        "Verified by local smoke and real local Plane write-back smoke.",
    ),
    (
        "agentpm-v1-06-serial-pipeline-engine",
        "Serial Pipeline Engine (coder -> tester -> reviewer)",
        states["Done"],
        "medium",
        "Stage orchestrator with ordered transitions and per-stage AgentRun creation.",
        "Implemented in SerialPipelineExecutor with deterministic order and handoff tests.",
    ),
    (
        "agentpm-v1-07-transition-approval-timeout",
        "Transition Approval Gate + Timeout Worker",
        states["Awaiting Review"],
        "medium",
        "Transition approval records, approve/reject decisions, reminders, and timeout blocking.",
        "Core service and timeout evaluation are implemented; productized operator API/UX remains review work.",
    ),
    (
        "agentpm-v1-08-one-level-rejection-rerun",
        "One-Level Rejection and Rerun",
        states["Done"],
        "medium",
        "Reject previous stage with required reason and spawn a rerun for the immediate previous stage.",
        "Implemented in RejectionService with immediate-previous-stage tests.",
    ),
    (
        "agentpm-v1-09-reliability-policy",
        "Reliability Policy (Retry + Fallback Agent Profile)",
        states["Done"],
        "medium",
        "Same-agent retry and optional backup-profile attempt for stage failures.",
        "Implemented in ReliabilityExecutor with retry, fallback, and blocked-state tests.",
    ),
    (
        "agentpm-v1-10-kpi-timeline-reporting",
        "KPI + Timeline Reporting API",
        states["Done"],
        "medium",
        "Project-level KPI endpoint and task timeline endpoint from audit data.",
        "Implemented in ReportingService and verified by tests and local smoke endpoints.",
    ),
    (
        "agentpm-v1-11-policy-configuration-ux",
        "Policy Configuration UX in Existing Plane Workflow",
        states["Backlog"],
        "low",
        "Minimal operator flow to configure pipeline order, approval boundaries, timeout, and role actions.",
        "Design notes exist; implementation remains a follow-up beyond the local MVP.",
    ),
    (
        "agentpm-v1-12-production-readiness",
        "Production Readiness Review (Runbook + SLO + Oncall Alerts)",
        states["In Progress"],
        "low",
        "Operational checklist for failure modes, alert thresholds, and runbook actions.",
        "MVP readiness docs exist; production alerting and real provider validation are still pending.",
    ),
]

for external_id, name, state, priority, summary, repo_status in backlog_specs:
    description = (
        "<p><strong>Synced from AgentRedmine current project.</strong></p>"
        f"<p>{summary}</p>"
        f"<p><strong>Current repo status:</strong> {repo_status}</p>"
        "<p>Source: docs/issues/agent-native-pm-v1-issue-backlog.md and docs/mvp-readiness.md.</p>"
    )
    backlog_issue, _ = Issue.objects.get_or_create(
        project=project,
        workspace=workspace,
        external_source="agentpm",
        external_id=external_id,
        defaults={
            "name": name,
            "description_html": description,
            "description_stripped": f"{summary} Current repo status: {repo_status}",
            "state": state,
            "priority": priority,
        },
    )
    backlog_issue.name = name
    backlog_issue.description_html = description
    backlog_issue.description_stripped = f"{summary} Current repo status: {repo_status}"
    backlog_issue.state = state
    backlog_issue.priority = priority
    backlog_issue.save()

token, _ = APIToken.objects.get_or_create(
    user=user,
    workspace=workspace,
    label="AgentPM Local MVP",
    is_service=True,
    defaults={
        "description": "Local AgentPM MVP verification token",
        "user_type": 0,
        "is_active": True,
        "allowed_rate_limit": "1000/min",
    },
)

print(f"export PLANE_API_BASE_URL=http://127.0.0.1:8000")
print(f"# Plane login: {email}")
print(f"# Plane password: {password}")
print(f"export PLANE_WORKSPACE_SLUG={workspace.slug}")
print(f"export PLANE_API_TOKEN={token.token}")
print(f"export PLANE_STATUS_FIELD=state")
print(
    "export PLANE_STATUS_MAP='"
    + "{"
    + f'"awaiting_review":"{states["Awaiting Review"].id}",'
    + f'"failed":"{states["Failed"].id}",'
    + f'"done":"{states["Done"].id}"'
    + "}'"
)
print(f"export REAL_PROJECT_ID={project.id}")
print(f"export REAL_TASK_ID={issue.id}")
print(f"export REAL_AGENT_ASSIGNEE=agent_openclaw_coder")
print(f"# Synced backlog work items: {len(backlog_specs)}")
PY
