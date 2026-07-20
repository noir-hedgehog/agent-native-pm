# Changelog

## mesh-v0.1.0 - unreleased

- Rename the public AGPL project to Mesh and import the customized Plane CE Console as a subtree.
- Add PostgreSQL-backed Agent identity, execution profiles, functional roles, Project Policy, Skill, Knowledge, and Loop runtime models.
- Add strict Page source formats, SKILL.md and Loop YAML contracts, explicit eligible-Agent handoff, and unassigned waiting semantics.
- Add Mesh-native MCP discovery, Policy, Skill, Knowledge, Loop, run, and stage-assignment tools while retaining `plane_*` compatibility.
- Add dedicated `mesh-runner` and `mesh-indexer` Celery queues and preserve Plane CE attribution and source availability.

## 0.2.0 - 2026-07-13

- Add production AgentPM containers, durable SQLite storage, health checks, structured logs, timeout worker, deployment, rollback, and backup tooling.
- Add asynchronous signed Plane assignment execution through a real OpenClaw bridge, loop prevention, and resumable approval gates.
- Add Plane-native Agent administration, token lifecycle UI, work item kind facade, cycle/module MCP workflow tools, and project execution views.
- Protect policy publishing and approval decisions with Plane Admin authorization and an internal AgentPM token.
- Keep Plane-native MCP identity token-bound and preserve Plane CE/AGPL attribution.
