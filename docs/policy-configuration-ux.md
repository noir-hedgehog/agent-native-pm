# Policy Configuration UX (Issue 11)

## Goal
Allow operators to configure one project policy (pipeline order, approval boundaries, timeout, and allowed actions by role) without code changes.

## Operator Flow

1. Open project settings and select `Agent Policy`.
2. Define ordered pipeline roles (example: `coder -> tester -> reviewer`).
3. Configure transition approval gates:
   - `coder -> tester`: no approval
   - `tester -> reviewer`: approval required
   - `reviewer -> done`: approval required
4. Configure timeout policy:
   - Reminder after 24h
   - Auto-block after 72h
5. Configure allowed actions by role:
   - `coder`: read_repo, write_patch, run_tests
   - `tester`: read_repo, run_tests
   - `reviewer`: read_reports, update_task_status
6. Save and publish policy version.

## Data Contract

```json
{
  "project_id": "proj_123",
  "pipeline_definition": ["coder", "tester", "reviewer"],
  "transition_approval_rules": {
    "coder->tester": false,
    "tester->reviewer": true,
    "reviewer->done": true
  },
  "transition_timeout_hours": {
    "reminder": 24,
    "block": 72
  },
  "allowed_actions_by_role": {
    "coder": ["read_repo", "write_patch", "run_tests"],
    "tester": ["read_repo", "run_tests"],
    "reviewer": ["read_reports", "update_task_status"]
  }
}
```

## Validation Rules

1. Pipeline must have at least 1 role and contain no duplicates.
2. Every transition rule key must refer to adjacent pipeline stages or final `->done`.
3. `block` timeout must be greater than `reminder` timeout.
4. Every pipeline role must have an entry in `allowed_actions_by_role`.
5. Unknown actions are rejected.
6. Policy updates create new version records and never overwrite history.

## Versioning and Audit

- Every publish creates a new immutable policy version.
- Fields stored with version metadata:
  - `version_id`
  - `project_id`
  - `published_by`
  - `published_at`
  - `change_note`
- Runtime execution reads latest published version only.

## Acceptance Mapping

- Team can configure one project policy without code changes.
- Misconfiguration validation prevents invalid transitions.
- Policy changes are versioned and auditable.
