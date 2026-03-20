# Local Integration Checklist

## 1. Preconditions

- Python 3.9+
- Repo on `main`
- Port `8080` available

## 2. Quick Run

```bash
./scripts/run_local_smoke.sh
```

Expected output:
- Step 1 returns HTTP `202` with `accepted=true`
- Metrics endpoint returns JSON with `task_count >= 1`
- Timeline endpoint returns non-empty events

## 3. Manual Verification

### 3.1 Start service
```bash
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

### 3.2 Send signed assignment webhook
```bash
python3 scripts/send_signed_assignment.py --secret dev-secret
```

### 3.3 Check metrics
```bash
curl -s http://127.0.0.1:8080/metrics/projects/proj_local
```

### 3.4 Check timeline
```bash
curl -s http://127.0.0.1:8080/tasks/task_local_001/timeline
```

## 4. Acceptance Criteria

- Signed request is accepted.
- Replaying same event id returns duplicate=true and no new session.
- Metrics endpoint responds with KPI fields.
- Timeline endpoint shows ordered events.

## 5. Troubleshooting

1. `INVALID_SIGNATURE`
- Secret mismatch between server and sender script.

2. `Address already in use`
- Stop previous process on 8080 or set `PORT` env.

3. Empty timeline
- Confirm same `task_id` used in webhook and timeline query.

4. No metrics updates
- Confirm `project_id` in webhook matches metrics query path.
