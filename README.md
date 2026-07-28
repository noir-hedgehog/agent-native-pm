# Mesh

Mesh is an agent-native collaboration platform built on Plane Community Edition. Plane supplies the Console, projects, work items, members, pages, cycles, permissions, and PostgreSQL foundation. Mesh adds Agent identity, functional roles, Policy, a project Skill Hub, cited Knowledge, and explicit Agent handoff Loops.

Mesh is not a general-purpose low-code automation editor. A Loop declares objectives, eligible roles, evidence, budgets, gates, and handoff boundaries. The previous Agent, a PM Agent, or a Human Admin explicitly selects the next eligible project Agent. With no selection, the Plane work item remains `Unassigned` while Mesh records `waiting_for_assignee`.

## License and source

Mesh is public under `AGPL-3.0-only` at [noir-hedgehog/mesh](https://github.com/noir-hedgehog/mesh). The Console is based on Plane Community Edition and retains Plane copyright, SPDX, license, and warranty notices.

- [LICENSE.txt](LICENSE.txt)
- [NOTICE.md](NOTICE.md)
- [MODIFICATIONS.md](MODIFICATIONS.md)
- [UPSTREAM.md](UPSTREAM.md)

## Architecture

- `plane/`: Mesh Console, Django API, PostgreSQL models, Plane-native MCP, Celery workers.
- `src/mesh/`: transition package for the earlier standalone orchestrator.
- `src/agentpm/`: one-release compatibility implementation for existing integrations.
- `skills/mesh-plane-workflow/`: standard MCP discovery and work-item workflow.
- `docs/`: protocol, deployment, API coverage, and compliance notes.

See [Mesh architecture](docs/mesh-architecture.md) for the identity, Policy, Skill, Knowledge, and Loop ownership boundaries.

Mesh-native data is stored in Plane PostgreSQL. `mesh-runner` only starts an Agent after an explicit assignment; `mesh-indexer` indexes Page-backed Knowledge. PostgreSQL, Valkey, RabbitMQ, MinIO, and worker ports remain private.

## Run locally

Initialize ignored local Console environment files before the first Compose run:

```bash
./scripts/init_mesh_console_env.sh
```

The generated values are development defaults. Replace every password and secret before deploying to a shared host.

```bash
./scripts/plane_service.sh up
docker compose -f plane/docker-compose.yml exec -T api python manage.py migrate
./scripts/seed_plane_mvp.sh
./scripts/seed_plane_agents.sh
./scripts/seed_plane_agent_guide_page.sh
./scripts/bootstrap_mesh_production.sh
```

Open [Mesh Console](http://127.0.0.1/). Service metadata and the AGPL source link are available at [http://127.0.0.1/mesh/](http://127.0.0.1/mesh/).

The transitional standalone runtime remains available:

```bash
PYTHONPATH=src MESH_WEBHOOK_SECRET=dev-secret python3 -m mesh.server
```

New settings use `MESH_*`. The matching `AGENTPM_*` name is read as a compatibility fallback for one release.

## Plane-native MCP

Each Human or Agent authenticates with its own Plane API token through `X-Api-Key`:

```text
/api/v1/workspaces/<workspace-slug>/mcp/
```

API-key clients can discover Mesh identity and read project-native resources under `/api/v1/workspaces/<workspace-slug>/mesh/`.

Identity cannot be switched with an `agent_id` argument. Before writing, use the `mesh-plane-workflow` Skill to discover the project, member, role, state, Policy, and eligible Agent identifiers.

```bash
./scripts/install_plane_agent_skill.sh
MESH_MCP_AGENT_ID=iris ./scripts/register_plane_native_mcp_openclaw.sh
openclaw mcp probe plane-native-iris --json
```

Existing `AGENTPM_MCP_AGENT_ID`, `plane_*` tools, the old Skill name, and its resource URI remain compatible for one release. Agent-native clients should adopt the `mesh_*` tools.

## Production source of truth

The shared production Console is available to the tailnet at
`http://100.79.187.62:8080/`. Local `127.0.0.1` services are development-only.
Set `MESH_ENVIRONMENT=production` on the shared host and leave the local default
as `development`; both `/mesh/` and `/mesh/health/` report this value.

Codex uses the secret-safe production wrapper without storing an API token in
its config:

```bash
MESH_PLANE_AGENT_ENV_FILE=.agentpm/plane-agent-env.production.sh \
  ./scripts/mesh_production_mcp_stdio.sh
```

The ignored environment file contains per-Agent Plane tokens. The repository
Skill is installed with `./scripts/install_plane_agent_skill.sh --codex-only`.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
docker compose -f plane/docker-compose.yml exec -T api pytest plane/tests/unit/mesh -q
docker compose -f plane/docker-compose.yml exec -T api pytest plane/tests/contract/api/test_mcp.py -q
docker compose -f plane/docker-compose.yml exec -T api python manage.py check
./scripts/verify_mvp.sh
```

## Deployment

Mesh is intended to be exposed through Tailscale by default. Do not publish PostgreSQL, Valkey, RabbitMQ, MinIO, or Celery worker ports.

```bash
./scripts/deploy_remote.sh --plane
./scripts/check_remote.sh
```

See [production deployment](docs/production-deployment.md), [Agent MCP guide](docs/agent-plane-mcp-guide.md), and [Plane API coverage](docs/plane-api-mcp-coverage.md).
