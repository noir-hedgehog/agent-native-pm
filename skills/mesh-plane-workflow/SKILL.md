---
name: mesh-plane-workflow
description: Use when an agent works with Plane through Mesh Plane-native MCP, especially to choose project/member/state ids, create or update work items, add project members, or recover from MCP tool errors.
---

# Mesh Plane Workflow

Plane-native MCP is a strict workflow facade. Your identity comes from the MCP server token (`X-Api-Key`). Do not pass `agent_id` to Plane-native MCP tools.

## Required Context Flow

1. Call `plane_get_me` before writing. Confirm the authenticated user, `agent_id`, and workspace role.
2. Call `plane_list_projects`. Choose the target `project_id`; keep passing it explicitly.
3. Call `plane_list_project_members(project_id)`. Use returned `agent_id` values for `target_agent_id` and `member_agent_id`.
4. Call `plane_list_states(project_id)` before passing `state` or `status`.
5. Call `plane_list_work_item_kinds(project_id)` before passing `work_item_kind`.
6. For assigned work, call `plane_get_work_item` or `plane_summarize_work_item` before updating.

## Parameter Rules

- `project_id`: from `plane_list_projects`.
- `work_item_id`: from `plane_list_work_items`, `plane_search_work_items`, or `plane_get_work_item`.
- `state` / `status`: state id, name, or group from `plane_list_states`.
- `target_agent_id`: short canonical agent id such as `iris`; never Plane user UUID or email.
- `member_agent_id`: short canonical agent id such as `iris`; never Plane user UUID or email.
- `labels`: ids or names from `plane_list_labels`.
- `work_item_kind`: strict enum from `plane_list_work_item_kinds`; currently `requirement`, `bug`, `task`, or `analysis`.
- `assignees`: existing project member ids/emails/usernames from `plane_list_project_members`.

## Common Workflows

Discover Mesh context before delegating:

1. `mesh_get_me`
2. `mesh_list_project_roles(project_id)`
3. `mesh_list_eligible_agents(project_id, roles, required_capabilities)`
4. `mesh_list_skills(project_id)` and `mesh_search_knowledge(project_id, query)` as needed
5. `mesh_assign_stage(project_id, stage_run_id, target_agent_id)` with an eligible short Agent id

Loop stages define objectives, evidence, roles, and policy boundaries. They do not prescribe which Skill, knowledge query, model, or internal reasoning steps an Agent must use.

Create work for an agent:

1. `plane_list_projects`
2. `plane_list_project_members(project_id)`
3. If the target agent is missing and you are Admin, call `plane_add_project_member(project_id, member_agent_id, role)`
4. `plane_list_states(project_id)`
5. `plane_list_work_item_kinds(project_id)`
6. `plane_create_work_item(project_id, name, target_agent_id, state, priority, description, work_item_kind)`

Plan with cycles or modules:

1. `plane_list_cycles(project_id)` or `plane_list_modules(project_id)`
2. Admin creates a missing cycle/module with `plane_create_cycle` or `plane_create_module`
3. Add assigned work with `plane_add_work_item_to_cycle` or `plane_add_work_item_to_module`

Add a registered agent to a project:

1. `plane_get_me`
2. `plane_list_agent_accounts`
3. `plane_list_project_members(project_id)`
4. `plane_add_project_member(project_id, member_agent_id, role)`

Update assigned work:

1. `plane_get_work_item(work_item_id, project_id)`
2. `plane_add_comment(work_item_id, body, project_id)` for progress notes
3. `plane_update_status(work_item_id, status, project_id)` when moving state
4. `plane_update_work_item(...)` only for fields you intend to change

## Roles

- Guest: read and comment.
- Member: create work items and write work assigned to its Plane user.
- Admin: assign work, create projects, and manage project membership.

## Error Recovery

If a tool returns `isError=true`, parse the JSON content:

- Read `error.message`.
- Follow `error.hint`.
- Call tools in `error.suggested_next_tools` before retrying.

Important errors:

- `invalid_agent_id`: use a short `agent_id` from `plane_list_agent_accounts` or `plane_list_project_members`; do not pass UUID/email.
- `target_not_project_member`: Admin should call `plane_add_project_member` before assigning/creating work for that agent.
- `insufficient_project_role`: switch to an Admin MCP server or ask a project Admin.
- `not_assigned`: ask an Admin to assign the work item to you before writing.
- `unknown_state`: call `plane_list_states(project_id)` and retry with a returned state.
- `invalid_work_item_kind`: call `plane_list_work_item_kinds(project_id)` and retry with a returned kind.
