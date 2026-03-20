# Production Readiness Runbook (Issue 12)

## SLOs

1. End-to-end task completion SLO
- Definition: time from assignment accepted to terminal successful handoff for final stage.
- Target: P95 <= 4 hours (rolling 7 days).

2. Approval responsiveness SLO
- Definition: time from approval creation to human decision.
- Target: P90 <= 24 hours.

3. Reliability SLO
- Definition: percentage of task sessions that do not end in `failed` or `blocked`.
- Target: >= 98% (rolling 30 days).

## Alert Rules

1. Stuck approvals
- Condition: pending approval age >= 24h (warning), >= 72h (critical).
- Action:
  - 24h: post reminder comment on task + notify operator channel.
  - 72h: auto-mark blocked + page oncall.

2. Repeated stage failures
- Condition: same stage role fails 3 times in 1 hour for same project.
- Action:
  - Trigger incident ticket.
  - Force fallback profile for next attempt.

3. Spike in rejection rate
- Condition: rejection_rate > 0.3 for 2 consecutive windows (30 min each).
- Action:
  - Freeze new policy rollouts.
  - Escalate to product + platform owners.

4. Adapter degradation
- Condition: adapter timeout/error ratio > 5% for 15 min.
- Action:
  - Switch traffic to backup profile set.
  - Open external dependency incident.

## Oncall Runbook

### A. Approval Timeout Incident
1. Query `/tasks/{task_id}/timeline` and confirm approval age.
2. Verify whether reviewer assignment is correct.
3. If misrouted, reassign reviewer and clear blocked state.
4. If no owner available, escalate to incident manager.

### B. Stage Failure Loop
1. Inspect last 3 failed runs and compare failure reasons.
2. If same root cause, force fallback profile.
3. If fallback also fails, pause pipeline and notify human owner.
4. Capture incident notes in task comments.

### C. Adapter Outage
1. Validate provider health endpoint and auth token validity.
2. Reduce run concurrency (if configurable).
3. Route to alternate provider/profile where possible.
4. Mark impacted sessions as blocked with standard reason.

## Standard Escalation Notes

- Timeout block note: `approval timed out after 72h; human intervention required`
- Failure block note: `retry and fallback exhausted; manual intervention required`

## Game-Day Exercise (Required)

Frequency: monthly

Scenario checklist:
1. Simulate stuck approval crossing 24h and 72h thresholds.
2. Simulate repeated stage failure causing fallback.
3. Simulate provider adapter outage.
4. Validate alerts fire and runbook steps can be executed within 30 min.

Evidence to capture:
- Alert timestamps
- Timeline screenshots/log snippets
- Mitigation actions taken
- Time to recovery

## Exit Criteria

- All three scenarios complete successfully.
- Oncall can restore pipeline progression without code changes.
- Postmortem with action items documented and assigned.
