# Plane API to MCP Coverage

Plane-native MCP is an agent-safe workflow facade, not a full mirror of every Plane API. Identity comes from the Plane `X-Api-Key` token, and every tool applies the authenticated user's workspace/project role.

Agent-facing usage guide: `docs/agent-plane-mcp-guide.md`. Seed it into the current Plane project with `./scripts/seed_plane_agent_guide_page.sh`.

## Covered in Plane-native MCP

| Plane API area | MCP coverage | Notes |
| --- | --- | --- |
| users/me | `plane_get_me` | Shows current token identity, workspace role, and bot/human flag. |
| projects | `plane_list_projects`, `plane_get_project_summary`, `plane_create_project` | Project creation remains workspace-admin only. |
| project members | `plane_list_project_members`, `plane_add_project_member`, `plane_add_workspace_user_to_project` | Admin-only writes; no token or invitation secrets. |
| states | `plane_list_states`, state/status fields in work item updates | State CRUD stays in Plane UI/admin flows. |
| labels | `plane_list_labels`, label assignment in `plane_update_work_item` | Label CRUD stays in Plane UI/admin flows. |
| work item kind | `plane_list_work_item_kinds`, strict `work_item_kind` fields on list/search/create/update | AgentPM facade backed by CE `kind:*` labels; it does not enable Plane paid Issue Type. |
| work items | `plane_list_work_items`, `plane_search_work_items`, `plane_get_work_item`, `plane_summarize_work_item`, `plane_create_work_item`, `plane_update_work_item`, `plane_update_status`, `plane_assign_work_item` | Member updates are limited to work items assigned to the authenticated Plane user. |
| comments | `plane_add_comment`, `plane_list_work_item_comments` | Guest can read/comment. |
| activities | `plane_list_work_item_activity` | Read-only timeline/audit context. |
| links | `plane_list_work_item_links`, `plane_add_work_item_link`, `plane_update_work_item_link`, `plane_delete_work_item_link` | Member writes require assignment; Admin can write any project work item. |
| relations | `plane_list_work_item_relations`, `plane_add_work_item_relation`, `plane_delete_work_item_relation` | Preserves Plane relation direction semantics such as `blocking` vs `blocked_by`. |
| agent accounts | `plane_list_agent_accounts` | Read-only bot account metadata; token secrets are never returned. |
| cycles | `plane_list_cycles`, `plane_create_cycle`, `plane_add_work_item_to_cycle`, `plane_remove_work_item_from_cycle` | Creation is Admin-only; Member writes require assignment. |
| modules | `plane_list_modules`, `plane_create_module`, `plane_add_work_item_to_module`, `plane_remove_work_item_from_module` | Creation is Admin-only; Member writes require assignment. |

## Deferred

| Plane API area | Why not V1 |
| --- | --- |
| attachments/assets | File upload/download follows the resource/stream proposal in `docs/mcp-attachment-stream-design.md`; no write tool is exposed yet. |
| intake | Triage/approval workflow is product-specific and should not be opened as generic agent write access yet. |
| estimates | Needs policy around estimation authority and project methodology. |
| state/label CRUD | Project workflow taxonomy should stay human/admin controlled in V1. |
| workspace invites/token management | Security-sensitive; remains Plane UI or human-admin CLI. |
| stickies/user preferences | Low value for agent project execution. |

## Permission Model

- All tools reject `agent_id`; callers cannot switch identity inside one MCP server.
- Guest can read project/work item context and comment.
- Member can create work items and write only work items assigned to that Plane user.
- Admin can write any work item in the project, assign work items, add existing workspace members/registered agents to projects, and create projects.
- Assignments only target active project members with role >= Member.
