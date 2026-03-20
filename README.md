# agent-native-pm

MVP orchestrator scaffold for Plane assignment webhook ingestion, signature validation, idempotency, and audit event capture.

## Run server

```bash
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

Server endpoint:

- `POST /webhooks/plane/assignment`

Required header:

- `X-Plane-Signature: sha256=<hmac_hex>`

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
