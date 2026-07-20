# Plane Paid Feature Inventory

This note is an implementation guide for the AgentPM-flavored Plane CE build. It is not legal advice. Keep Plane's AGPL-3.0 license, copyright, SPDX headers, notices, and source-availability obligations intact.

Sources checked:

- Plane docs: `Project Work Item Types` is marked Pro.
- Plane docs: `Workspace Work Item Types` is marked Enterprise Grid.
- Local Plane pricing matrix: `plane/apps/web/core/constants/plans.tsx`.
- Local CE code: `plane/packages/constants/src/commercial.ts` hides commercial entry points through `AGENTPM_HIDE_COMMERCIAL_ENTRYPOINTS`.

## Do Not Expose As Plane Paid Features

These should stay hidden as Plane product-plan entry points in our CE build:

| Area | Plane plan signal | Notes |
| --- | --- | --- |
| Work item types | Pro+ project types; Enterprise Grid workspace types | Do not expose native Plane type settings or market it as unlocked Plane Pro. |
| Custom properties | Pro+ project properties; Business+ workspace properties/rollups | Prefer AgentPM-owned metadata or labels for MVP. |
| Work item templates | Pro+ / coming soon in local matrix | Keep hidden. |
| Page templates and page exports | Pro+ | Keep hidden unless implemented as AgentPM-owned export. |
| Time tracking and worklogs | One/Pro/Business tiered | Keep Plane paid UI hidden; AgentPM can implement separate execution timing. |
| Bulk operations beyond CE basics | One/Pro tiered | Keep upsell banners hidden. |
| Active cycles across workspace | One+ | Keep upsell hidden unless we build an AgentPM view. |
| Epics / initiatives / checkpoints | Pro+ / Business+ depending feature | Avoid native paid UI. AgentPM may model higher-level work separately. |
| Gantt dependencies / work item transfers / auto-transfer cycles | Pro+ | Avoid exposing Plane paid controls. |
| Public/private/secret project variants | Pro+ | Keep current CE project access model unless AgentPM defines its own policy. |
| Shared/published views | Pro+ | Keep native paid publishing hidden. |
| Dashboards/widgets, progress charts, cycle reports, insights, custom reports | Pro+/Business+ | AgentPM reports should be separate artifacts, not unlocked Plane paid screens. |
| PQL / advanced search | Pro+ | Keep hidden unless AgentPM adds its own search facade. |
| Guests beyond CE expectations | One+ in plan matrix | We currently use Plane roles carefully for bot agents; do not expose billing language. |
| Approvals, admin interface, audit logs | Business+ / coming soon | AgentPM policy approvals are our own feature, not Plane paid approval UI. |
| Automations/workflows | Pro+ / Business+ | AgentPM orchestration is allowed as our own layer. |
| Integrations marketplace: GitHub/Slack/Zapier/Zendesk/Freshdesk | Pro+ / coming soon | Keep native paid/marketplace UI hidden. |
| Storage quotas and larger uploads | Cloud-only paid matrix | Do not show cloud plan limits in self-host CE UI. |
| SAML/OIDC/domain security/2FA/password policy/LDAP | One+/Pro+/Enterprise depending feature | Keep native paid security entry points hidden unless already CE-supported in this build. |
| One-click deployment, marketplace apps, private managed deployments | Self-host paid/Enterprise | Not relevant to local AgentPM build. |
| Paid support/SLA/contact sales | Paid plans | Remove sales and billing CTAs from UI. |

## AgentPM-Owned Equivalents We Can Build

These are safe directions because they do not claim to unlock Plane paid capabilities; they are AgentPM workflow features layered on top of CE primitives.

| Need | Recommended AgentPM implementation |
| --- | --- |
| Bug vs requirement vs task vs analysis | Use an AgentPM `work_item_kind` facade mapped to CE labels first. Avoid native Plane `IssueType` UI. |
| Agent/human role separation | Use Plane `User.is_bot`, workspace/project roles, AgentPM registry, and MCP policy. |
| Project policy / pipeline roles | Store in AgentPM policy API/SQLite and display in the existing Agent Policy page. |
| Agent assignment and permissions | Use Plane project membership + AgentPM MCP policy checks. |
| Execution timing | Store AgentRun timestamps and summaries in AgentPM, not Plane time tracking. |
| Reports / dashboards | Generate AgentPM reports or MCP artifacts instead of enabling Plane dashboards. |
| Approvals | Use AgentPM `TransitionApproval` records and Plane comments/status write-back. |
| Roadmap | Link to our GitHub issues/project board, not Plane paid roadmap/community CTAs. |

## UI Cleanup Policy

- Hide Billing & Plans navigation and pages from routable UI.
- Hide Upgrade/Pro badges and paid-plan modals.
- Replace Plane forum/community/sales links with AgentPM Docs/Roadmap/GitHub links.
- Keep Plane copyright, license, version information, and source obligations visible where applicable.
- Do not remove CE work tracking modules such as projects, work items, cycles, modules, pages, labels, states, or estimates.
