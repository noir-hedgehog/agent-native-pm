# MCP Attachment Resource Design

Attachments remain intentionally outside the current Plane-native MCP tool set. A normal JSON tool call should not carry large base64 payloads or expose arbitrary server file paths.

## Proposed V1.1 contract

1. `plane_prepare_attachment_upload(work_item_id, filename, content_type, size, sha256)` validates project role, assignment, size, and media type, then returns a short-lived upload id.
2. The client uploads bytes to an authenticated MCP resource endpoint in bounded chunks. The resource URI is scoped to the token user and upload id.
3. `plane_complete_attachment_upload(upload_id)` verifies size and SHA-256, creates the Plane asset/attachment record, and returns non-secret metadata.
4. `plane_list_work_item_attachments(work_item_id)` and a read resource expose metadata and authorized streaming downloads.

## Security requirements

- Guest is read-only; Member uploads only to assigned work items; Admin may upload anywhere in the project.
- Enforce configured file size and content-type allowlists before accepting bytes.
- Never accept local paths or remote URLs as a substitute for uploaded content.
- Upload ids expire, are single-use, and are bound to workspace, project, work item, and Plane user.
- Logs and MCP results contain filename, size, digest, and asset id, never signed object-store credentials.
- Partial objects are garbage-collected and virus scanning can be inserted before completion.

This design can map to Plane assets and MinIO without making MinIO credentials or internal ports agent-visible.
