# agent-native-pm

MVP orchestrator scaffold for Plane assignment webhook ingestion, signature validation, idempotency, and audit event capture.

## Run server

```bash
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

Server endpoint:

- `POST /webhooks/plane/assignment`

Required header:

- `X-Plane-Signature: <hmac_hex>` (also accepts `sha256=<hmac_hex>`)

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Local smoke test (real request flow)

Use this to validate:
- signed webhook ingestion
- task session creation + idempotency
- metrics and timeline query endpoints

```bash
./scripts/run_local_smoke.sh
```

Manual equivalent:

```bash
# 1) start server
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server

# 2) send one signed assignment webhook (new terminal)
python3 scripts/send_signed_assignment.py --secret dev-secret

# 3) check project metrics
curl -s http://127.0.0.1:8080/metrics/projects/proj_local

# 4) check task timeline
curl -s http://127.0.0.1:8080/tasks/task_local_001/timeline
```

## OpenClaw real API integration

See:
- `docs/openclaw-integration.md`

Quick probe:

```bash
python3 scripts/openclaw_probe.py --base-url "$OPENCLAW_BASE_URL"
```
