# Git Workflow

## 1. Current recommendation

- Use feature branches now.
- Do not use worktree yet.
- Keep `main` clean and deployable.

## 2. Branch naming

All working branches must use `codex/` prefix.

Suggested patterns:
- `codex/spec-v1`
- `codex/issue-1-webhook-idempotency`
- `codex/issue-2-session-model`
- `codex/issue-3-openclaw-adapter`

## 3. Branch strategy by phase

### 3.1 Spec phase (now)
- Branch: `codex/spec-v1`
- Scope: PRD, plan, issue backlog, API contracts

### 3.2 Implementation phase
- One issue per branch.
- Merge small vertical slices frequently.
- Avoid long-running mega branches.

## 4. Commit convention

Use small, reviewable commits.

Format:
- `<type>(<scope>): <summary>`

Types:
- `docs`: documentation changes
- `feat`: new behavior
- `fix`: bug fix
- `refactor`: structural change with no behavior change
- `test`: tests only
- `chore`: tooling/config

Examples:
- `docs(spec): add agent-native PM v1 spec`
- `feat(webhook): add assignment dedupe handling`
- `test(orchestrator): add transition approval tests`

## 5. Pull request convention

Each PR should include:
- Problem statement
- Scope (what is included, what is excluded)
- Acceptance criteria checklist
- Test evidence (logs/screenshots/results)
- Rollback note (how to disable/revert)

## 6. When to introduce worktree

Introduce worktree only when at least one condition is true:
- Two or more agents are coding in parallel.
- Two or more branches must be active in the same day.
- Context switching cost becomes noticeable.

If none of the above is true, keep single working directory + branch flow.

## 7. Worktree operating model (future)

When enabled:
- One branch per worktree.
- One agent profile per worktree.
- No shared edits across worktrees.
- Integration branch receives merges in dependency order.

Suggested layout:
- `../wt-issue-1-webhook`
- `../wt-issue-2-session`
- `../wt-3-adapter`

## 8. Safety rules

- Never commit directly to `main`.
- Never use destructive git operations without explicit approval.
- Rebase/squash only before merge, not during active collaboration.
- If unexpected changes appear, stop and confirm before proceeding.

## 9. Daily operator checklist

1. Pull latest `main`.
2. Create or switch to target `codex/...` branch.
3. Implement one vertical slice.
4. Run tests for changed scope.
5. Open PR with acceptance criteria evidence.
6. Merge and delete branch.
